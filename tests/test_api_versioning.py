"""v1 라우팅과 기존 경로의 쿠키·응답 호환성을 검사합니다."""

from datetime import datetime, timezone

import psycopg
import pytest

from app import main


def test_openapi_lists_versioned_business_routes_only(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/health" in paths
    for path in (
        "/news/feed", "/news/{article_id}", "/news/{article_id}/like",
        "/user/anonymous", "/category", "/subcategory",
    ):
        assert "/v1" + path in paths
        assert path not in paths


@pytest.mark.parametrize("path", ["/news/feed", "/v1/news/feed"])
def test_feed_versions_accept_same_cookie(client, fake_db, path):
    assert client.post("/v1/user/anonymous").status_code == 200
    fake_db.set(results=[[]])
    response = client.post(path, json={})
    assert response.status_code == 200
    assert response.json()["items"] == []


@pytest.mark.parametrize("prefix", ["", "/v1"])
def test_detail_versions_use_reader_cookie_and_return_article(reader_client, fake_db, prefix):
    article = {key: None for key in main.ArticleDetail.model_fields}
    article.update(
        article_id="detail-1", title="상세 기사", paragraphs=["기사 본문"], tags=["검증"],
        category="사회", published_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
        is_synthetic=True, is_liked=True,
    )
    connection = fake_db.set(results=[[article]])
    response = reader_client.get(prefix + "/news/detail-1")
    assert response.status_code == 200
    assert response.json()["content"]["is_liked"] is True
    assert response.json()["content"]["paragraphs"] == ["기사 본문"]
    reader_id = reader_client.post("/user/anonymous").json()["reader_id"]
    assert connection.executed[0][1] == (reader_id, "detail-1")


def test_v1_detail_requires_signed_cookie(client):
    assert client.get("/v1/news/detail-1", params={"reader_id": "arbitrary"}).status_code == 401


def test_v1_detail_missing_article_returns_404(reader_client, fake_db):
    fake_db.set(results=[[]])
    assert reader_client.get("/v1/news/missing").status_code == 404


def test_v1_detail_database_error_returns_503(reader_client, fake_db):
    fake_db.set(error=psycopg.OperationalError("test failure"))
    assert reader_client.get("/v1/news/detail-1").status_code == 503


def test_feed_excludes_body_from_response(reader_client, fake_db):
    article = {key: None for key in main.ArticleDetail.model_fields}
    article.update(
        article_id="feed-1", title="목록 기사", paragraphs=["상세 전용 본문"], tags=[],
        category="사회", published_at=datetime(2026, 11, 20, tzinfo=timezone.utc),
        is_synthetic=True, is_liked=False,
    )
    fake_db.set(results=[[article]])
    response = reader_client.post("/v1/news/feed", json={})
    assert response.status_code == 200
    assert "paragraphs" not in response.json()["items"][0]
    assert "paragraphs" not in main.FeedItem.model_fields
