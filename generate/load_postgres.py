"""JSONL 기사를 PostgreSQL에 적재합니다. 같은 id는 최신 입력으로 갱신합니다."""

import argparse
import fcntl
from datetime import date, datetime
import json
import os
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

import psycopg
from dotenv import load_dotenv
from psycopg.types.json import Jsonb


ROOT = Path(__file__).resolve().parent

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

CREATE_LIKES_TABLE = """
CREATE TABLE IF NOT EXISTS public.article_likes (
    reader_id TEXT NOT NULL,
    article_id TEXT NOT NULL REFERENCES public.news_articles(id),
    liked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (reader_id, article_id)
)
"""

CREATE_LIKE_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS public.article_like_history (
    change_id UUID PRIMARY KEY,
    reader_id TEXT NOT NULL,
    article_id TEXT NOT NULL REFERENCES public.news_articles(id),
    action TEXT NOT NULL CHECK (action IN ('like', 'unlike')),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""


def ensure_schema(cursor):
    """기사·좋아요 상태·이력 테이블을 준비합니다. 기존 데이터는 수정하지 않습니다."""
    cursor.execute(CREATE_TABLE)
    cursor.execute(CREATE_LIKES_TABLE)
    cursor.execute(CREATE_LIKE_HISTORY_TABLE)


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


def validate_image_base_url(value):
    value = value.strip()
    parsed = urlsplit(value)
    if (parsed.scheme not in ('http', 'https') or not parsed.netloc
            or parsed.query or parsed.fragment):
        raise ValueError('image 기본 URL은 query·fragment 없는 http(s) 주소여야 합니다.')
    return value.rstrip('/')


def resolve_image_url(article, source_path, output_root, image_base_url):
    """JSONL 기준 상대 경로를 공개 루트 URL에 연결합니다. 업로드는 수행하지 않습니다."""
    existing_url = article.get('image_url')
    if existing_url:
        return existing_url
    image_path = article.get('image_path')
    if not image_path:
        return None
    if not isinstance(image_path, str):
        raise ValueError('image_path: 문자열 또는 null이어야 합니다.')
    local_path = Path(image_path)
    if local_path.is_absolute():
        raise ValueError('image_path: JSONL 기준 상대 경로여야 합니다.')
    image_file = (source_path.resolve().parent / local_path).resolve()
    try:
        relative = image_file.relative_to(output_root.expanduser().resolve())
    except ValueError:
        raise ValueError('image_path가 --output-root 밖을 가리킵니다. 이미지 공개 루트를 확인하세요.')
    return validate_image_base_url(image_base_url) + '/' + quote(relative.as_posix(), safe='/')


def read_articles(path, *, output_root=None, image_base_url='http://localhost:8001'):
    output_root = output_root if output_root is not None else ROOT / 'output_with_thumbnail'

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
                image_url = resolve_image_url(article, path, output_root, image_base_url)
                values = []
                for name in COLUMNS:
                    if name == "raw_article":
                        value = Jsonb(article)
                    elif name == "source_file":
                        value = str(path)
                    elif name in JSON_COLUMNS:
                        value = Jsonb(article[name])
                    elif name == "image_url":
                        value = image_url
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


def parse_load_date(value):
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value:
            raise ValueError
        return parsed
    except ValueError:
        raise argparse.ArgumentTypeError('날짜는 YYYY-MM-DD 형식이어야 합니다.')


def date_input_files(output_root, selected_date):
    """이전 run 폴더를 먼저, 새 날짜 폴더는 파일 번호순으로 선택합니다."""
    legacy = sorted(output_root.glob(f'run-{selected_date:%Y%m%d}-*/articles.jsonl'))
    day = output_root / selected_date.isoformat()
    numbered = []
    if day.is_dir():
        numbered = [p for p in day.glob('articles-*.jsonl')
                    if re.fullmatch(r'articles-\d+\.jsonl', p.name)]
        numbered.sort(key=lambda p: int(p.stem.split('-')[1]))
        if (day / 'articles.jsonl').is_file():
            legacy.append(day / 'articles.jsonl')
    files = legacy + numbered
    if not files:
        raise ValueError(f'{selected_date}: 기사 JSONL이 없습니다: {output_root}')
    return files


def read_input_files(paths, *, output_root=None, image_base_url='http://localhost:8001'):
    # 생성기가 갱신 중인 JSONL을 부분 적재하지 않습니다.
    unique = {}
    input_rows = 0
    for path in paths:
        lock_path = path.parent / f'.{path.stem}.lock'
        lock = lock_path.open('r') if lock_path.exists() else None
        try:
            if lock is not None:
                try:
                    fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
                except BlockingIOError:
                    raise ValueError(f'생성 중인 파일입니다. 생성 종료 후 적재하세요: {path}')
            if not path.read_text(encoding='utf-8-sig').strip():
                print(f'빈 기사 파일 건너뜀: {path}')
                continue
            rows = read_articles(path, output_root=output_root, image_base_url=image_base_url)
            input_rows += len(rows)
            for row in rows:
                unique[row[0]] = row
            print(f'입력: {path} ({len(rows)}행)')
        finally:
            if lock is not None:
                lock.close()
    if not unique:
        raise ValueError('적재할 기사가 없습니다.')
    return list(unique.values()), input_rows


def load_project_env():
    # 실행 위치와 무관하게 backend/.env를 읽고 기존 환경변수는 유지합니다.
    load_dotenv(dotenv_path=ROOT.parent / '.env', override=False)


def main():
    load_project_env()
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--input", type=Path, help="적재할 JSONL 파일 하나")
    inputs.add_argument("--date", type=parse_load_date, help="해당 날짜의 기사 JSONL 전체 적재: YYYY-MM-DD")
    parser.add_argument("--output-root", type=Path, default=ROOT / 'output_with_thumbnail',
                        help="날짜 폴더를 찾을 생성 결과 루트")
    parser.add_argument("--image-base-url", default=os.getenv('IMAGE_BASE_URL', 'http://localhost:8001'),
                        help="이미지 공개 루트 URL. IMAGE_BASE_URL 또는 기본 http://localhost:8001")
    parser.add_argument("--host", default=os.getenv("PGHOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.getenv("PGPORT", "5433")))
    parser.add_argument("--dbname", default=os.getenv("PGDATABASE", "newsdb"))
    parser.add_argument("--user", default=os.getenv("PGUSER", "recommend"))
    parser.add_argument("--validate-only", action="store_true", help="DB 연결 없이 파일 검증")
    args = parser.parse_args()
    try:
        image_base_url = validate_image_base_url(args.image_base_url)
        output_root = args.output_root.expanduser().resolve()
        paths = ([args.input.expanduser().resolve()] if args.input else
                 date_input_files(output_root, args.date))
        rows, input_rows = read_input_files(paths, output_root=output_root, image_base_url=image_base_url)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    if args.validate_only:
        for row in rows[:3]:
            print(f"이미지 URL: {row[0]} → {row[COLUMNS.index('image_url')]}")
        print(f"검증 완료: 파일 {len(paths)}개 / 원본 {input_rows}행 / 고유 기사 {len(rows)}건")
        return

    # 비밀번호는 프로젝트 .env·기존 환경변수의 PGPASSWORD 또는 ~/.pgpass로 전달합니다.
    # 전체 적재는 한 트랜잭션으로 처리하며 실패 시 모두 롤백합니다.
    with psycopg.connect(
        host=args.host, port=args.port, dbname=args.dbname,
        user=args.user, connect_timeout=10,
    ) as connection:
        with connection.cursor() as cursor:
            ensure_schema(cursor)
            cursor.executemany(UPSERT, rows)
            cursor.execute("SELECT count(*) FROM public.news_articles")
            total = cursor.fetchone()[0]
    print(f"적재 완료: 파일 {len(paths)}개 / 원본 {input_rows}행 / 고유 기사 {len(rows)}건 / 테이블 전체 {total}건")
    print("저장 테이블: public.news_articles")


if __name__ == "__main__":
    main()
