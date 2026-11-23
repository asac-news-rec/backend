"""FastAPI가 사용하는 연결 풀을 테스트용 임시 PostgreSQL로 검증합니다."""

from uuid import uuid7

import psycopg
import pytest
from fastapi.testclient import TestClient

from app import config, db, main, repository
from generate.load_postgres import ensure_schema


@pytest.fixture
def pooled_client(postgres_test_dsn, monkeypatch, reader_cookie_settings):
    # 기존 API 테스트와 달리 앱의 연결 함수를 교체하지 않는다.
    with psycopg.connect(postgres_test_dsn) as conn:
        for setting, value in {
            "PGHOST": conn.info.host,
            "PGPORT": conn.info.port,
            "PGDATABASE": conn.info.dbname,
            "PGUSER": conn.info.user,
            "PGPASSWORD": conn.info.password,
        }.items():
            monkeypatch.setattr(config, setting, value)

    monkeypatch.setenv("DB_POOL_MAX_SIZE", "1")
    with TestClient(main.app, base_url=reader_cookie_settings) as client:
        yield client


@pytest.fixture
def committed_article(postgres_test_dsn):
    article_id = f"pool-{uuid7()}"
    # API 연결의 커밋·롤백 결과를 별도의 PostgreSQL 연결에서 확인한다.
    with psycopg.connect(postgres_test_dsn, autocommit=True) as observer:
        with observer.transaction(), observer.cursor() as cursor:
            ensure_schema(cursor)
            cursor.execute(
                """
                INSERT INTO public.news_articles (
                    id, title, category, published_at, paragraphs, tags,
                    is_synthetic, raw_article, source_file
                )
                VALUES (%s, '풀 테스트 기사', '경제', now(), '[]', '[]', TRUE, '{}', 'test')
                """,
                (article_id,),
            )

        try:
            yield observer, article_id
        finally:
            with observer.transaction():
                observer.execute(
                    "DELETE FROM public.article_like_history WHERE article_id = %s", (article_id,)
                )
                observer.execute(
                    "DELETE FROM public.article_likes WHERE article_id = %s", (article_id,)
                )
                observer.execute("DELETE FROM public.news_articles WHERE id = %s", (article_id,))


def test_pool_reuses_postgres_connection(pooled_client):
    with db.connect() as first:
        first_pid = first.info.backend_pid

    assert pooled_client.get("/health").status_code == 200

    with db.connect() as second:
        assert second.info.backend_pid == first_pid


@pytest.mark.parametrize("path, body", [
    ("/v1/news/feed", {}),
    ("/category", None),
])
def test_pool_exhaustion_returns_503(pooled_client, path, body):
    assert pooled_client.post("/user/anonymous").status_code == 200
    # 풀 크기가 1이므로 보유 중인 연결을 반납할 때까지 API에 줄 연결이 없다.
    with db.connect():
        response = pooled_client.post(path, json=body)
        assert response.status_code == 503

    assert pooled_client.get("/health").status_code == 200


def read_like_state(observer, article_id, reader_id):
    params = (article_id, reader_id)
    liked = observer.execute(
        "SELECT 1 FROM public.article_likes WHERE article_id = %s AND reader_id = %s",
        params,
    ).fetchone()
    history = observer.execute(
        """
        SELECT action FROM public.article_like_history
        WHERE article_id = %s AND reader_id = %s
        ORDER BY change_id
        """,
        params,
    ).fetchall()
    return liked is not None, [action for (action,) in history]


def test_like_and_unlike_commit(pooled_client, committed_article):
    observer, article_id = committed_article
    reader_id = pooled_client.post("/user/anonymous").json()["reader_id"]
    path = f"/news/{article_id}/like"

    assert pooled_client.put(path).status_code == 200
    assert read_like_state(observer, article_id, reader_id) == (True, ["like"])

    response = pooled_client.request("DELETE", path)
    assert response.status_code == 200
    assert read_like_state(observer, article_id, reader_id) == (False, ["like", "unlike"])


@pytest.mark.parametrize("method", ["PUT", "DELETE"])
def test_like_change_rolls_back_on_history_error(
    pooled_client, committed_article, monkeypatch, method
):
    observer, article_id = committed_article
    reader_id = pooled_client.post("/user/anonymous").json()["reader_id"]
    path = f"/news/{article_id}/like"

    # 해제 테스트의 사전 상태는 API를 호출해 커밋한 좋아요다.
    if method == "DELETE":
        assert pooled_client.put(path).status_code == 200
    expected_state = read_like_state(observer, article_id, reader_id)

    # 상태를 바꾼 직후 이력 INSERT가 PostgreSQL의 기본 키 제약에 걸리게 한다.
    duplicate_id = uuid7()
    observer.execute(
        """
        INSERT INTO public.article_like_history (change_id, reader_id, article_id, action)
        VALUES (%s, 'conflict-reader', %s, 'like')
        """,
        (duplicate_id, article_id),
    )
    monkeypatch.setattr(repository, "uuid7", lambda: duplicate_id)

    response = pooled_client.request(method, path)
    assert response.status_code == 503
    assert read_like_state(observer, article_id, reader_id) == expected_state
    assert pooled_client.get("/health").status_code == 200
