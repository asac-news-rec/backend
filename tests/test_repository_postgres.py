from app.repository import fetch_news, fetch_news_detail, set_like


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


def test_detail_returns_body_and_reader_specific_like(postgres_connection, insert_articles):
    insert_articles([("detail-1", "상세 기사", "사회", None, "2026-11-20T00:00:00Z")])
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


def test_detail_returns_false_after_unlike(postgres_connection, insert_articles):
    insert_articles([("detail-1", "상세 기사", "사회", None, "2026-11-20T00:00:00Z")])
    set_like(postgres_connection, "reader-a", "detail-1", True)
    set_like(postgres_connection, "reader-a", "detail-1", False)
    assert fetch_news_detail(postgres_connection, "detail-1", "reader-a")["is_liked"] is False


def test_detail_returns_none_for_missing_article(postgres_connection):
    assert fetch_news_detail(postgres_connection, "missing-detail", "reader-a") is None



def test_fetch_news_uses_id_to_continue_at_the_same_published_at(
    postgres_connection, insert_articles,
):
    published_at = "2026-11-10T09:00:00Z"
    insert_articles([
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
