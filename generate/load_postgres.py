"""JSONL 기사를 PostgreSQL에 적재합니다. 같은 id는 최신 입력으로 갱신합니다."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path

import psycopg
from psycopg.types.json import Jsonb


CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS public.news_articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    subtitle TEXT,
    summary TEXT,
    paragraphs JSONB NOT NULL,
    tags JSONB NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    published_at TIMESTAMPTZ NOT NULL,
    author TEXT,
    publisher TEXT,
    language TEXT,
    is_synthetic BOOLEAN NOT NULL,
    url TEXT,
    image_url TEXT,
    image_caption TEXT,
    raw_article JSONB NOT NULL,
    source_file TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""

COLUMNS = (
    "id", "title", "subtitle", "summary", "paragraphs", "tags", "category",
    "subcategory", "published_at", "author", "publisher", "language",
    "is_synthetic", "url", "image_url", "image_caption",
    "raw_article", "source_file",
)
JSON_COLUMNS = {"paragraphs", "tags"}
UPSERT = (
    f"INSERT INTO public.news_articles ({', '.join(COLUMNS)}) "
    f"VALUES ({', '.join(['%s'] * len(COLUMNS))}) "
    "ON CONFLICT (id) DO UPDATE SET "
    + ", ".join(f"{name} = EXCLUDED.{name}" for name in COLUMNS if name != "id")
    + ", loaded_at = CURRENT_TIMESTAMP"
)


def read_articles(path):
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                article = json.loads(line)
                for key in ("id", "title", "category", "published_at"):
                    if not isinstance(article[key], str) or not article[key].strip():
                        raise ValueError(f"{key}: 비어 있지 않은 문자열이 필요합니다")
                timestamp = datetime.fromisoformat(article["published_at"])
                if timestamp.tzinfo is None:
                    raise ValueError("published_at: 시간대가 필요합니다")
                for key in ("paragraphs", "tags"):
                    if not isinstance(article[key], list) or not all(
                        isinstance(value, str) for value in article[key]
                    ):
                        raise ValueError(f"{key}: 문자열 배열이 필요합니다")
                article.pop("generation", None)
                if not isinstance(article["is_synthetic"], bool):
                    raise ValueError("is_synthetic: boolean이 필요합니다")
                values = []
                for name in COLUMNS:
                    if name == "raw_article":
                        value = Jsonb(article)
                    elif name == "source_file":
                        value = str(path)
                    elif name in JSON_COLUMNS:
                        value = Jsonb(article[name])
                    elif name == "published_at":
                        value = timestamp
                    else:
                        value = article.get(name)
                    values.append(value)
                rows.append(tuple(values))
            except (ValueError, KeyError, TypeError) as exc:
                raise ValueError(f"{path}:{line_number}: {exc}") from exc
    if not rows:
        raise ValueError(f"적재할 기사가 없습니다: {path}")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="적재할 articles.jsonl 경로")
    parser.add_argument("--host", default=os.getenv("PGHOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5433")))
    parser.add_argument("--dbname", default=os.getenv("PGDATABASE", "newsdb"))
    parser.add_argument("--user", default=os.getenv("PGUSER", "recommend"))
    parser.add_argument("--validate-only", action="store_true", help="DB 연결 없이 파일 검증")
    args = parser.parse_args()
    path = args.input.expanduser().resolve()
    rows = read_articles(path)
    if args.validate_only:
        print(f"검증 완료: {len(rows)}행, 고유 기사 {len({row[0] for row in rows})}건")
        return

    # 비밀번호는 PGPASSWORD 또는 ~/.pgpass를 통해 전달합니다.
    # 전체 적재는 한 트랜잭션으로 처리하며 실패 시 모두 롤백합니다.
    with psycopg.connect(
        host=args.host, port=args.port, dbname=args.dbname,
        user=args.user, connect_timeout=10,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(CREATE_TABLE)
            cursor.execute("ALTER TABLE public.news_articles DROP COLUMN IF EXISTS generation")
            cursor.execute("UPDATE public.news_articles SET raw_article = raw_article - 'generation' WHERE raw_article ? 'generation'")
            cursor.executemany(UPSERT, rows)
            cursor.execute("SELECT count(*) FROM public.news_articles")
            total = cursor.fetchone()[0]
    print(f"적재 완료: 입력 {len(rows)}행 / 테이블 전체 {total}건")
    print("저장 테이블: public.news_articles")


if __name__ == "__main__":
    main()
