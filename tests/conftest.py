"""FastAPI와 테스트용 임시 PostgreSQL을 사용하는 테스트의 공용 도구."""

import os
import secrets
from collections import deque
from contextlib import nullcontext

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg.rows import dict_row

from app import main
from generate.load_postgres import ensure_schema


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self._last = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.conn.executed.append((" ".join(sql.split()), params))
        if self.conn.error is not None:
            raise self.conn.error
        # 미리 넣어 둔 결과를 execute 순서대로 하나씩 꺼낸다.
        self._last = self.conn.results.popleft() if self.conn.results else None
        return self

    def fetchall(self):
        return list(self._last or [])

    def fetchone(self):
        if isinstance(self._last, list):
            return self._last[0] if self._last else None
        return self._last


class FakeConnection:
    """psycopg.Connection 대용. results에는 execute 호출 순서대로 돌려줄 결과를 넣는다."""

    def __init__(self, results=None, error=None):
        self.results = deque(results or [])
        self.error = error
        self.executed = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self):
        return FakeCursor(self)

    def execute(self, sql, params=None):
        return self.cursor().execute(sql, params)


@pytest.fixture
def fake_db(monkeypatch):
    """app.main.connect()가 FakeConnection을 돌려주도록 바꾼다."""

    state = {"conn": FakeConnection(), "connect_error": None}

    def fake_connect():
        if state["connect_error"] is not None:
            raise state["connect_error"]
        return state["conn"]

    monkeypatch.setattr(main, "connect", fake_connect)

    class Controller:
        def set(self, results=None, error=None):
            state["conn"] = FakeConnection(results, error)
            return state["conn"]

        def fail_connect(self, message="connection refused"):
            state["connect_error"] = psycopg.OperationalError(message)

    return Controller()


@pytest.fixture
def reader_cookie_settings(monkeypatch):
    monkeypatch.setenv("READER_COOKIE_SECRET", secrets.token_urlsafe(32))
    monkeypatch.setenv("READER_COOKIE_SECURE", "true")
    return "https://testserver"


@pytest.fixture
def client(fake_db, reader_cookie_settings):
    with TestClient(main.app, base_url=reader_cookie_settings) as test_client:
        yield test_client


@pytest.fixture
def reader_client(client):
    response = client.post("/user/anonymous")
    assert response.status_code == 200
    return client


@pytest.fixture
def postgres_test_dsn():
    dsn = os.environ.get("POSTGRES_TEST_DSN")
    if not dsn:
        pytest.skip("Set POSTGRES_TEST_DSN to run the PostgreSQL integration test")
    return dsn


@pytest.fixture
def postgres_connection(postgres_test_dsn):
    with psycopg.connect(postgres_test_dsn, row_factory=dict_row) as connection:
        # 테스트마다 스키마와 데이터를 준비하고 끝나면 롤백한다.
        with connection.transaction(force_rollback=True):
            with connection.cursor() as cursor:
                ensure_schema(cursor)
            yield connection


@pytest.fixture
def insert_articles(postgres_connection):
    def insert(rows):
        with postgres_connection.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO public.news_articles (
                    id, title, category, subcategory, published_at,
                    paragraphs, tags, is_synthetic, raw_article, source_file
                )
                VALUES (%s, %s, %s, %s, %s, '[]', '[]', TRUE, '{}', 'test')
                """,
                rows,
            )

    return insert


@pytest.fixture
def feed_filter_articles(insert_articles):
    insert_articles([
        ("stock-old", "이전 증권 기사", "경제", "증권", "2026-11-09T01:00:00Z"),
        ("stock-new", "최신 증권 기사", "경제", "증권", "2026-11-10T01:00:00Z"),
        ("estate", "부동산 기사", "경제", "부동산", "2026-11-11T01:00:00Z"),
        ("politics", "다른 대분류 기사", "정치", "증권", "2026-11-12T01:00:00Z"),
    ])


@pytest.fixture
def postgres_client(postgres_connection, monkeypatch, reader_cookie_settings):
    # API가 아직 커밋하지 않은 테스트 기사를 읽도록 fixture의 연결을 넘긴다.
    # 연결과 트랜잭션의 종료는 postgres_connection이 맡는다.
    monkeypatch.setattr(main, "connect", lambda: nullcontext(postgres_connection))
    with TestClient(main.app, base_url=reader_cookie_settings) as test_client:
        response = test_client.post("/user/anonymous")
        assert response.status_code == 200
        yield test_client
