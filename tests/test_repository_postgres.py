from app.repository import fetch_news


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
