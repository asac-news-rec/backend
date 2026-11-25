"""추론 서버 호출과 순서 변경 테스트."""

import pytest
import requests

from app import inference

ITEMS = [{"article_id": name} for name in ("a", "b", "c")]


class FakeResponse:
    def __init__(self, body, status=200):
        self.body, self.status = body, status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(str(self.status))

    def json(self):
        return self.body


def ranked(*pairs):
    return {"model_version": "pctr@7", "features_as_of": "2026-11-25T10:00:00+09:00",
            "ranked": [{"article_id": a, "pctr": p, "rank": i}
                       for i, (a, p) in enumerate(pairs, start=1)]}


def run(monkeypatch, response):
    monkeypatch.setenv("INFERENCE_URL", "http://inference/")
    calls = []

    def fake_post(url, **kwargs):
        calls.append((url, kwargs))
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(inference.requests, "post", fake_post)
    return inference.rerank(ITEMS, "req", "reader", "2026-11-25T01:00:00+00:00"), calls


def test_rerank_orders_by_rank_and_appends_unscored(monkeypatch):
    items, calls = run(monkeypatch, FakeResponse(ranked(("c", 0.3), ("a", 0.1))))
    assert [i["article_id"] for i in items] == ["c", "a", "b"]
    assert [i["score"] for i in items] == [0.3, 0.1, None]
    assert {i["model_version"] for i in items} == {"pctr@7"}
    assert {i["features_as_of"] for i in items} == {None}
    url, kwargs = calls[0]
    assert url == "http://inference/v1/rank"
    assert kwargs["timeout"] == 0.5
    assert kwargs["json"]["candidates"] == ["a", "b", "c"]


@pytest.mark.parametrize("response", [
    requests.Timeout("slow"),
    FakeResponse({}, status=503),
    FakeResponse({"unexpected": 1}),
    FakeResponse(ranked(("x", 0.1))),
    FakeResponse(ranked(("a", 0.2), ("a", 0.1))),
    FakeResponse(ranked(("a", float("nan")))),
    FakeResponse(ranked(("a", True))),
    FakeResponse(ranked(("a", "0.1"))),
    FakeResponse(ranked(("a", 10 ** 400))),
    FakeResponse({"model_version": "pctr@7", "ranked": [
        {"article_id": "a", "pctr": 0.1, "rank": 2}, {"article_id": "b", "pctr": 0.2, "rank": 1}]}),
])
def test_rerank_falls_back_to_latest_order(monkeypatch, response):
    items, _ = run(monkeypatch, response)
    assert [i["article_id"] for i in items] == ["a", "b", "c"]
    assert {i["model_version"] for i in items} == {"fallback"}
    assert {i["score"] for i in items} == {None}


def test_rerank_disabled_without_url(monkeypatch):
    monkeypatch.delenv("INFERENCE_URL", raising=False)
    monkeypatch.setattr(inference.requests, "post", lambda *a, **k: pytest.fail("호출하면 안 됨"))
    items = inference.rerank(ITEMS, "req", "reader", "t")
    assert [i["article_id"] for i in items] == ["a", "b", "c"]
    assert {i["model_version"] for i in items} == {None}


def test_feed_cursor_stays_in_latest_order(
    postgres_client, postgres_connection, monkeypatch,
):
    from datetime import datetime, timedelta, timezone

    from tests.helpers import insert_articles

    newest = datetime(2026, 11, 10, tzinfo=timezone.utc)
    insert_articles(postgres_connection, [
        (f"a{i}", f"제목 {i}", "경제", "증권", newest - timedelta(minutes=i))
        for i in range(1, 26)
    ])

    def reverse_rank(url, json, timeout):
        ids = json["candidates"][::-1]
        return FakeResponse(ranked(*[(a, 1 - n / 100) for n, a in enumerate(ids)]))

    monkeypatch.setenv("INFERENCE_URL", "http://inference")
    monkeypatch.setattr(inference.requests, "post", reverse_rank)
    first = postgres_client.post("/v1/news/feed", json={}).json()
    assert [i["article_id"] for i in first["items"]] == [f"a{i}" for i in range(20, 0, -1)]
    assert first["next_cursor"]["article_id"] == "a20"
    second = postgres_client.post("/v1/news/feed", json={"cursor": first["next_cursor"]}).json()
    assert {i["article_id"] for i in second["items"]} == {f"a{i}" for i in range(21, 26)}
    row = postgres_connection.execute(
        "SELECT score, model_version, features_as_of FROM public.news_impressions WHERE article_id = 'a20'"
    ).fetchone()
    assert row == {"score": 1.0, "model_version": "pctr@7", "features_as_of": None}
