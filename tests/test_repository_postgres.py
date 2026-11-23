from app.repository import fetch_news, fetch_news_detail, set_like,save_news_impressions
from datetime import datetime, timezone
from uuid import uuid7
import pytest
from psycopg.errors import UniqueViolation

from tests.helpers import insert_articles


def test_fetch_news_filters_by_category_and_subcategory_in_newest_order(
    postgres_connection, feed_filter_articles,
):
    articles, has_more = fetch_news(
        postgres_connection,
        reader_id="test-reader",
        category="경제",
        subcategory="증권",
    )

    assert [article["article_id"] for article in articles] == ["stock-new", "stock-old"]
    assert not has_more


def test_detail_returns_body_and_reader_specific_like(postgres_connection):
    insert_articles(postgres_connection, [("detail-1", "상세 기사", "사회", None, "2026-11-20T00:00:00Z")])
    postgres_connection.execute(
        "UPDATE news_articles SET paragraphs = '[\"상세 본문\"]'::jsonb WHERE id = %s",
        ("detail-1",),
    )
    set_like(postgres_connection, "reader-a", "detail-1", True)
    liked = fetch_news_detail(postgres_connection, "detail-1", "reader-a")
    other = fetch_news_detail(postgres_connection, "detail-1", "reader-b")
    assert liked["paragraphs"] == ["상세 본문"]
    assert liked["is_liked"] is True
    assert other["article_id"] == "detail-1"
    assert other["is_liked"] is False


def test_detail_returns_false_after_unlike(postgres_connection):
    insert_articles(postgres_connection, [("detail-1", "상세 기사", "사회", None, "2026-11-20T00:00:00Z")])
    set_like(postgres_connection, "reader-a", "detail-1", True)
    set_like(postgres_connection, "reader-a", "detail-1", False)
    assert fetch_news_detail(postgres_connection, "detail-1", "reader-a")["is_liked"] is False


def test_detail_returns_none_for_missing_article(postgres_connection):
    assert fetch_news_detail(postgres_connection, "missing-detail", "reader-a") is None



def test_fetch_news_uses_id_to_continue_at_the_same_published_at(
    postgres_connection,
):
    published_at = "2026-11-10T09:00:00Z"
    insert_articles(postgres_connection, [
        ("article-b", "기사 B", "경제", "증권", published_at),
        ("article-a", "기사 A", "경제", "증권", published_at),
        ("article-c", "다른 카테고리", "스포츠", None, published_at),
    ])

    first, _ = fetch_news(postgres_connection, reader_id="test-reader", category="경제")
    assert [article["article_id"] for article in first] == ["article-b", "article-a"]

    articles, has_more = fetch_news(
        postgres_connection,
        reader_id="test-reader",
        category="경제",
        after=(first[0]["published_at"], first[0]["article_id"]),
    )

    assert [article["article_id"] for article in articles] == ["article-a"]
    assert not has_more

# 각 테스트에서 사용할 피드 응답입니다.
# pytest.fixture: pytest에 “테스트 함수가 impression_response를 인자로 요청하면, 이 함수를 실행한 반환값을 넣어 줘.”라고 등록
@pytest.fixture
def impression_response():
    return {
        "request_id": str(uuid7()),
        "served_at": datetime.now(timezone.utc).isoformat(),
        "items": [
            {
                "impression_id": str(uuid7()),
                "article_id": "article-100",
                "position": 1,
            },
            {
                "impression_id": str(uuid7()),
                "article_id": "article-200",
                "position": 2,
            },
        ],
    }

# 1. 응답의 기사 수만큼 저장되고, 저장값이 입력값과 같은지 확인합니다.
def test_save_news_impressions_stores_response_values(
    postgres_connection,
    impression_response,
):
    save_news_impressions(
        postgres_connection,
        "reader-test",
        impression_response,
    )

    with postgres_connection.cursor() as cur:
        cur.execute(
            """
            SELECT
                impression_id,
                request_id,
                reader_id,
                article_id,
                position,
                served_at
            FROM public.news_impressions
            WHERE request_id = %s
            ORDER BY position
            """,
            (impression_response["request_id"],),
        )
        rows = cur.fetchall()

    assert len(rows) == 2

    for row, item in zip(
        rows,
        impression_response["items"],
        strict=True,
    ):
        # PostgreSQL의 UUID 객체를 문자열로 바꿔 응답값과 비교합니다.
        assert str(row["impression_id"]) == item["impression_id"]
        assert str(row["request_id"]) == impression_response["request_id"]
        assert row["reader_id"] == "reader-test"
        assert row["article_id"] == item["article_id"]
        assert row["position"] == item["position"]
        assert row["served_at"] == datetime.fromisoformat(
            impression_response["served_at"]
        )
# 3. 같은 impression_id를 다시 저장하면 중복 오류가 나는지 확인합니다.
def test_save_news_impressions_rejects_duplicate_ids(
    postgres_connection,
    impression_response,
):
    # 최초 저장은 성공해야 합니다.
    save_news_impressions(
        postgres_connection,
        "reader-test",
        impression_response,
    )

    # 동일한 응답을 다시 저장하면 기본 키 중복 오류가 발생해야 합니다.
    with pytest.raises(UniqueViolation):
        with postgres_connection.transaction():
            save_news_impressions(
                postgres_connection,
                "reader-test",
                impression_response,
            )

    # 실패한 재저장 때문에 최초 기록이 없어지거나 늘어나지 않아야 합니다.
    with postgres_connection.cursor() as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS count
            FROM public.news_impressions
            WHERE request_id = %s
            """,
            (impression_response["request_id"],),
        )
        row = cur.fetchone()

    assert row["count"] == 2
