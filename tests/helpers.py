"""테스트에서 명시적으로 호출하는 공용 함수."""


def insert_articles(conn, rows):
    """전달받은 DB 연결로 기사 목록을 저장합니다."""
    with conn.cursor() as cursor:
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
