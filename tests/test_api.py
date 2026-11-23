"""FastAPI 엔드포인트 테스트."""

from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from uuid import UUID

import psycopg
import pytest
from itsdangerous import TimestampSigner

from tests.helpers import insert_articles


# ---------- /health ----------

def test_health_ok(client, fake_db):
    fake_db.set(results=[{"ok": 1}])
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "database": 1}


def test_health_returns_503_when_db_down(client, fake_db):
    fake_db.fail_connect()
    res = client.get("/health")
    assert res.status_code == 503


# ---------- /v1/news/feed ----------

@pytest.fixture
def feed_page_articles(postgres_connection):
    newest = datetime(2026, 11, 10, tzinfo=timezone.utc)
    insert_articles(postgres_connection, [
        (f"a{i}", f"제목 {i}", "경제", "증권", newest - timedelta(minutes=i - 1))
        for i in range(1, 26)
    ])


def test_feed_first_page_has_next_cursor(postgres_client, feed_page_articles):
    res = postgres_client.post("/v1/news/feed", json={})

    assert res.status_code == 200
    body = res.json()
    assert [item["article_id"] for item in body["items"]] == [
        f"a{i}" for i in range(1, 21)
    ]
    cursor = body["next_cursor"]
    assert cursor["article_id"] == "a20"
    assert datetime.fromisoformat(cursor["published_at"]) == datetime.fromisoformat(
        body["items"][-1]["published_at"]
    )
    assert cursor["returned_count"] == 20
    assert [item["position"] for item in body["items"]] == list(range(1, 21))
    UUID(body["request_id"])
    assert len({item["impression_id"] for item in body["items"]}) == 20


def test_feed_continues_after_newer_article_is_inserted(
    postgres_client, feed_page_articles, postgres_connection,
):
    first = postgres_client.post("/v1/news/feed", json={})
    assert first.status_code == 200
    cursor = first.json()["next_cursor"]

    insert_articles(postgres_connection, [
        ("new", "새 최신 기사", "경제", "증권", datetime(2026, 11, 11, tzinfo=timezone.utc)),
    ])
    res = postgres_client.post("/v1/news/feed", json={"cursor": cursor})

    assert res.status_code == 200
    body = res.json()
    assert [item["article_id"] for item in body["items"]] == [
        f"a{i}" for i in range(21, 26)
    ]
    assert body["next_cursor"] is None
    assert [item["position"] for item in body["items"]] == [21, 22, 23, 24, 25]


def test_feed_filters_articles(postgres_client, feed_filter_articles):
    res = postgres_client.post(
        "/v1/news/feed",
        json={"category": "경제", "subcategory": "증권"},
    )

    assert res.status_code == 200
    body = res.json()
    assert [item["article_id"] for item in body["items"]] == ["stock-new", "stock-old"]
    assert body["next_cursor"] is None


def test_feed_saves_returned_impressions(
    postgres_client, postgres_connection, feed_page_articles,
):
    reader = postgres_client.post("/v1/user/anonymous")
    assert reader.status_code == 200
    reader_id = reader.json()["reader_id"]

    response = postgres_client.post("/v1/news/feed", json={})
    assert response.status_code == 200
    body = response.json()

    with postgres_connection.cursor() as cur:
        cur.execute(
            """
            SELECT impression_id, request_id, reader_id, article_id, position, served_at
            FROM public.news_impressions
            WHERE request_id = %s
            ORDER BY position
            """,
            (body["request_id"],),
        )
        rows = cur.fetchall()

    assert len(rows) == len(body["items"]) == 20
    for row, item in zip(rows, body["items"], strict=True):
        assert str(row["impression_id"]) == item["impression_id"]
        assert str(row["request_id"]) == body["request_id"]
        assert row["reader_id"] == reader_id
        assert row["article_id"] == item["article_id"]
        assert row["position"] == item["position"]
        assert row["served_at"] == datetime.fromisoformat(body["served_at"])


def test_feed_returns_503_when_impression_save_fails(
    postgres_client, feed_page_articles, monkeypatch,
):
    monkeypatch.setattr(
        "app.main.save_news_impressions",
        Mock(side_effect=psycopg.OperationalError("테스트용 로그 저장 실패")),
    )

    response = postgres_client.post("/v1/news/feed", json={})

    assert response.status_code == 503
    assert response.json() == {"detail": "뉴스 전송내역 저장에 실패하였습니다."}


def test_feed_returns_503_on_db_error(reader_client, fake_db):
    fake_db.set(error=psycopg.OperationalError("boom"))
    res = reader_client.post("/v1/news/feed", json={})
    assert res.status_code == 503


def test_feed_rejects_invalid_body(reader_client):
    cursor = {"published_at": "2026-11-10T09:00:00Z", "article_id": "a20", "returned_count": 20}
    for invalid in (
        {**cursor, "published_at": "2026-11-10T09:00:00"},
        {**cursor, "article_id": ""},
        {**cursor, "returned_count": -1},
    ):
        res = reader_client.post("/v1/news/feed", json={"cursor": invalid})
        assert res.status_code == 422
    assert reader_client.post("/v1/news/feed").status_code == 422


# ---------- 좋아요 ----------

def test_like_sets_like(reader_client, fake_db):
    # advisory lock, 기사 존재 확인, INSERT RETURNING, 이력 INSERT 순서
    conn = fake_db.set(results=[None, {"id": "a1"}, {"article_id": "a1"}, None])
    res = reader_client.put("/news/a1/like")

    assert res.status_code == 200
    assert res.json() == {"article_id": "a1", "is_liked": True, "changed": True}
    history_sql, history_params = conn.executed[3]
    assert "article_like_history" in history_sql
    assert history_params[3] == "like"


def test_unlike_when_already_unliked_is_unchanged(reader_client, fake_db):
    # DELETE RETURNING이 아무 행도 돌려주지 않으면 changed=False, 이력도 남기지 않음
    conn = fake_db.set(results=[None, {"id": "a1"}, None])
    res = reader_client.request("DELETE", "/news/a1/like")

    assert res.json() == {"article_id": "a1", "is_liked": False, "changed": False}
    assert len(conn.executed) == 3


def test_like_returns_404_for_missing_article(reader_client, fake_db):
    fake_db.set(results=[None, None])
    res = reader_client.put("/news/nope/like")
    assert res.status_code == 404


def test_like_returns_503_on_db_error(reader_client, fake_db):
    fake_db.set(error=psycopg.OperationalError("boom"))
    res = reader_client.put("/news/a1/like")
    assert res.status_code == 503


# ---------- 사용자·카테고리 ----------

def test_create_anonymous_user_returns_uuid7_and_reuses_cookie(client):
    response = client.post("/user/anonymous")
    reader_id = response.json()["reader_id"]
    assert UUID(reader_id).version == 7
    assert response.headers["cache-control"] == "no-store"
    cookie_header = response.headers["set-cookie"]
    assert "news_reader=" in cookie_header
    assert "HttpOnly" in cookie_header
    assert "Secure" in cookie_header
    assert "SameSite=lax" in cookie_header

    assert client.post("/user/anonymous").json() == {"reader_id": reader_id}


def test_feed_rejects_missing_or_tampered_reader_cookie(client):
    assert client.post("/v1/news/feed", json={}).status_code == 401

    issued = client.post("/user/anonymous")
    payload, signature = issued.cookies["news_reader"].rsplit(".", 1)
    replacement = "A" if signature[0] != "A" else "B"
    tampered = f"{payload}.{replacement}{signature[1:]}"
    client.cookies.clear()

    response = client.post(
        "/v1/news/feed", json={}, headers={"Cookie": f"news_reader={tampered}"}
    )
    assert response.status_code == 401


def test_feed_rejects_expired_reader_cookie(client, monkeypatch):
    with monkeypatch.context() as expired_time:
        expired_time.setattr(TimestampSigner, "get_timestamp", lambda self: 0)
        assert client.post("/user/anonymous").status_code == 200

    assert client.post("/v1/news/feed", json={}).status_code == 401


def test_like_uses_reader_id_from_cookie(reader_client, fake_db):
    reader_id = reader_client.post("/user/anonymous").json()["reader_id"]
    conn = fake_db.set(results=[None, {"id": "a1"}, {"article_id": "a1"}, None])

    response = reader_client.put("/news/a1/like", json={"reader_id": "another-reader"})

    assert response.status_code == 200
    assert conn.executed[2][1] == (reader_id, "a1")


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_like_requires_reader_cookie(client, fake_db, method):
    conn = fake_db.set()
    response = client.request(method, "/news/a1/like")

    assert response.status_code == 401
    assert conn.executed == []


def test_category_list(client, fake_db):
    fake_db.set(results=[[{"category": "경제"}, {"category": "정치"}]])
    res = client.post("/category")
    assert res.json() == {"category_list": ["경제", "정치"]}


def test_subcategory_list(client, fake_db):
    conn = fake_db.set(results=[[{"subcategory": "증권"}, {"subcategory": "부동산"}]])
    res = client.post("/subcategory", json={"category": "경제"})

    assert res.json() == {"sub_category_list": ["증권", "부동산"]}
    assert conn.executed[0][1] == ("경제",)


@pytest.mark.parametrize("path, body", [
    ("/category", None),
    ("/subcategory", {"category": "경제"}),
])
def test_category_lookup_returns_503_on_db_error(client, fake_db, path, body):
    fake_db.set(error=psycopg.OperationalError("query failed"))

    response = client.post(path, json=body)

    assert response.status_code == 503


def test_subcategory_list_is_sorted_and_distinct(postgres_client, postgres_connection):
    published_at = "2026-11-10T09:00:00Z"
    insert_articles(postgres_connection, [
        ("subcategory-z", "Z 기사", "경제", "Zeta", published_at),
        ("subcategory-a", "A 기사", "경제", "Alpha", published_at),
        ("subcategory-a2", "다른 A 기사", "경제", "Alpha", published_at),
        ("subcategory-null", "소분류 없는 기사", "경제", None, published_at),
        ("subcategory-other", "다른 카테고리 기사", "스포츠", "Beta", published_at),
    ])

    response = postgres_client.post("/subcategory", json={"category": "경제"})

    assert response.status_code == 200
    assert response.json() == {"sub_category_list": ["Alpha", "Zeta"]}


def test_subcategory_requires_category(client):
    assert client.post("/subcategory", json={"category": ""}).status_code == 422
