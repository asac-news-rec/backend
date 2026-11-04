import psycopg
from fastapi import FastAPI,HTTPException
from .db import connect
import json
from uuid import uuid7

def fetch_news(conn,reader_id,offset):
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
            ORDER BY a.published_at DESC, a.id DESC
            -- 다음 페이지 확인용 1개를 포함해 최대 21개 조회
            LIMIT 21 OFFSET %s
        """, (reader_id,offset))
        rows = cur.fetchall()
        # row[:20] 실제 응답에는 최대 20개만 포함, len(rows)>20 : 21번째 기사가 있으면 다음 page가 있다는 것
        return rows[:20], len(rows) > 20

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