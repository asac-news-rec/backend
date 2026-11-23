import psycopg
from fastapi import FastAPI,HTTPException
from .db import connect
import json
from datetime import datetime
from uuid import uuid7

def fetch_news(
    conn,
    reader_id: str,
    category: str | None = None,
    subcategory: str | None = None,
    *,
    after: tuple[datetime, str] | None = None,
):
    params = [reader_id, category, category, subcategory, subcategory]
    cursor_condition = ""
    if after is not None:
        # 이전 페이지의 마지막 기사 다음부터 조회한다.
        cursor_condition = "AND (a.published_at, a.id) < (%s, %s)"
        params.extend(after)

    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT
                a.id AS article_id,
                a.title,
                a.subtitle,
                a.summary,
                a.tags,
                a.category,
                a.subcategory,
                a.published_at,
                a.author,
                a.publisher,
                a.language,
                a.is_synthetic,
                a.url,
                a.image_url,
                a.image_caption,
                (l.reader_id IS NOT NULL) AS is_liked
            FROM public.news_articles AS a
            LEFT JOIN public.article_likes AS l
                ON l.article_id = a.id
                AND l.reader_id = %s
            WHERE (%s::text IS NULL OR a.category = %s)
                AND (%s::text IS NULL OR a.subcategory = %s)
                {cursor_condition}
            ORDER BY a.published_at DESC, a.id DESC
            LIMIT 21
        """, params)
        rows = cur.fetchall()

    # 21번째 기사는 다음 페이지가 있는지 확인하는 데 사용한다.
    return rows[:20], len(rows) > 20


# category고유값 추출
def fetch_big_category(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                distinct(a.category)
            FROM public.news_articles AS a
            order by category
        """)
        return cur.fetchall()

# category값을 받아서 sub_category값을 추출
def fetch_sub_category(conn,category):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT DISTINCT a.subcategory
            FROM public.news_articles AS a
            WHERE a.category = %s
                AND a.subcategory IS NOT NULL
            ORDER BY a.subcategory
            """, (category,))
        return cur.fetchall()

class ArticleNotFound(Exception):
    pass

def set_like(conn, reader_id, article_id, desired):
    with conn.cursor() as cur:
        # 같은 사용자·기사에 대한 동시 변경을 순서대로 처리
        key = json.dumps([reader_id, article_id], separators=(",", ":"))

        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            (key,),
        )

        # 기사 존재 확인. 처리 도중 해당 기사가 삭제되는 것도 방지
        cur.execute(
            """
            SELECT id
            FROM public.news_articles
            WHERE id = %s
            FOR KEY SHARE
            """,
            (article_id,),
        )

        if cur.fetchone() is None:
            raise ArticleNotFound()

        if desired:
            # 좋아요 설정
            cur.execute(
                """
                INSERT INTO public.article_likes (reader_id, article_id)
                VALUES (%s, %s)
                ON CONFLICT (reader_id, article_id) DO NOTHING
                RETURNING article_id
                """,
                (reader_id, article_id),
            )
        else:
            # 좋아요 해제
            cur.execute(
                """
                DELETE FROM public.article_likes
                WHERE reader_id = %s AND article_id = %s
                RETURNING article_id
                """,
                (reader_id, article_id),
            )

        # 실제로 추가·삭제된 행이 있으면 True
        changed = cur.fetchone() is not None

        # 상태가 바뀐 경우에만 이력 저장
        if changed:
            change_id = uuid7()
            cur.execute(
                """
                INSERT INTO public.article_like_history
                    (change_id, reader_id, article_id, action)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    change_id,
                    reader_id,
                    article_id,
                    "like" if desired else "unlike",
                ),
            )

    return {
        "article_id": article_id,
        "is_liked": desired,
        "changed": changed,
    }

def fetch_news_detail(
    conn,
    article_id :str,
    reader_id:str
):

    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                a.id AS article_id,
                a.title,
                a.subtitle,
                a.summary,
                a.paragraphs,
                a.tags,
                a.category,
                a.subcategory,
                a.published_at,
                a.author,
                a.publisher,
                a.language,
                a.is_synthetic,
                a.url,
                a.image_url,
                a.image_caption,
                (l.reader_id IS NOT NULL) AS is_liked
            FROM public.news_articles AS a
            LEFT JOIN public.article_likes AS l
                ON l.article_id = a.id
                AND l.reader_id = %s
            WHERE a.id = %s
        """, (reader_id,article_id))
        row = cur.fetchone()
    return row

def save_news_impressions(
    conn,
    reader_id :str,
    response:dict
):
    rows = [
        (item['impression_id'],
         response['request_id'],
         reader_id,
         item['article_id'],
         item['position'],
         response['served_at'],
         None,
         None,
         None
         )
         for item in response['items']
    ]

    with conn.cursor() as cur:
        cur.executemany("""
            INSERT INTO public.news_impressions(
                impression_id,
                request_id,
                reader_id,
                article_id,
                position,
                served_at,
                score,
                model_version,
                features_as_of
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,rows)
