"""OpenRouter로 가상 뉴스 기사와 640×360 PNG 썸네일을 생성합니다."""

import argparse
import base64
import csv
from datetime import date, datetime
import fcntl
import hashlib
from io import BytesIO
import json
import os
from pathlib import Path
import random
import uuid
from zoneinfo import ZoneInfo

from PIL import Image, ImageOps
from pydantic import Field, ValidationError
import psycopg
import requests

from .article_schema import Draft
from .load_postgres import article_row, resolve_image_url, upsert_articles, validate_image_base_url


ROOT = Path(__file__).resolve().parent
OPENROUTER_URL = "https://openrouter.ai/api/v1"


def load_taxonomy(path):
    result = {}
    with path.open(encoding='utf-8-sig', newline='') as f:
        # 첫 줄은 컬럼명, 이후 각 행은 딕셔너리로 읽습니다.
        reader = csv.DictReader(f)
        # 필수 컬럼이 모두 있는지 확인합니다.
        if not {'대분류', '중분류'} <= set(reader.fieldnames or []):
            raise ValueError('CSV에 대분류, 중분류 컬럼이 필요합니다.')
        for row in reader:
            category, subcategory = row['대분류'].strip(), row['중분류'].strip()
            if category:
                # 키가 없으면 추가하고 같은 중분류 리스트를 가져옵니다.
                subcategories = result.setdefault(category, [])
                if subcategory and subcategory not in subcategories:
                    subcategories.append(subcategory)
    if not result:
        raise ValueError('유효한 분류가 없습니다.')
    return result


def load_publishers(path):
    """CSV에서 중복 없는 언론사 목록을 읽습니다."""
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        if 'publisher' not in (reader.fieldnames or []):
            raise ValueError('언론사 CSV에 publisher 컬럼이 필요합니다.')
        publishers = list(dict.fromkeys(
            row['publisher'].strip() for row in reader if row.get('publisher', '').strip()
        ))
    if not publishers:
        raise ValueError('언론사 CSV에 유효한 언론사가 없습니다.')
    return publishers


def article_timestamp():
    return datetime.now(ZoneInfo("Asia/Seoul"))


def save_articles(path, articles):
    temporary = path.with_suffix(".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            for article in articles:
                stream.write(json.dumps(article, ensure_ascii=False) + "\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


class ArticleWithImagePrompt(Draft):
    image_prompt: str = Field(
        min_length=1,
        description="기사 내용을 바탕으로 한 영문 실사풍 썸네일 묘사",
    )


def openrouter_post(session, endpoint, payload):
    response = session.post(f"{OPENROUTER_URL}/{endpoint}", json=payload, timeout=(10, 120))
    response.raise_for_status()
    result = response.json()
    if not isinstance(result, dict) or result.get("error"):
        raise ValueError("OpenRouter가 정상적인 응답을 반환하지 않았습니다.")
    return result


def generate_article(session, model, category, subcategory, published_at):
    response = openrouter_post(session, "chat/completions", {
        "model": model,
        "provider": {"require_parameters": True},
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "news_article",
                "strict": True,
                "schema": {
                    **ArticleWithImagePrompt.model_json_schema(),
                    "additionalProperties": False,
                },
            },
        },
        "messages": [
            {
                "role": "system",
                "content": (
                    "추천 시스템용 한국어 가상 뉴스를 작성한다. 사건, 인물, 기관은 허구로 만들고 "
                    "실제 기사 문장을 복제하지 않는다. 본문은 5~9문단, 각 문단은 100~220자의 "
                    "일반 텍스트로 작성한다. 본문의 구체적인 키워드를 중복 없이 태그로 쓴다. "
                    "image_prompt는 기사에 맞는 실사풍 장면을 영문으로 묘사한다. "
                    "이미지에 글자, 로고, 실존 인물을 포함하지 않는다."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"대분류: {category}\n중분류: {subcategory or '지정 없음'}\n"
                    f"발행일: {published_at.date().isoformat()}\n"
                    f"다양성 식별자: {uuid.uuid4().hex}"
                ),
            },
        ],
    })
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("OpenRouter 응답에 기사 본문이 없습니다.") from error
    return ArticleWithImagePrompt.model_validate_json(content)


def save_thumbnail(session, model, prompt, path):
    response = openrouter_post(session, "images", {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "aspect_ratio": "16:9",
        "output_format": "png",
    })
    try:
        encoded_image = response["data"][0]["b64_json"]
        image_bytes = base64.b64decode(encoded_image, validate=True)
    except (KeyError, IndexError, TypeError, ValueError) as error:
        raise ValueError("OpenRouter 응답에 유효한 썸네일 데이터가 없습니다.") from error
    with Image.open(BytesIO(image_bytes)) as image:
        thumbnail = ImageOps.fit(image.convert("RGB"), (640, 360), Image.Resampling.LANCZOS)
        temporary_path = path.with_suffix(".tmp")
        try:
            thumbnail.save(temporary_path, format="PNG")
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)


def upload_thumbnail(path, output_root, bucket_name):
    """기존 공개 버킷 경로에 PNG를 저장하고 재시도 시 같은 파일인지 확인합니다."""
    from google.api_core.exceptions import GoogleAPIError, PreconditionFailed
    from google.auth.exceptions import DefaultCredentialsError
    from google.cloud import storage

    object_name = "images/" + path.resolve().relative_to(output_root.resolve()).as_posix()
    try:
        with storage.Client() as client:
            blob = client.bucket(bucket_name).blob(object_name)
            try:
                blob.upload_from_filename(str(path), content_type="image/png", if_generation_match=0)
            except PreconditionFailed:
                blob.reload()
                local_hash = base64.b64encode(hashlib.md5(path.read_bytes(), usedforsecurity=False).digest()).decode("ascii")
                if blob.md5_hash != local_hash:
                    raise ValueError("GCS에 같은 경로의 다른 이미지가 있습니다.")
    except (GoogleAPIError, DefaultCredentialsError):
        raise ValueError("GCS 썸네일 업로드에 실패했습니다. 버킷과 실행 계정 권한을 확인하세요.") from None


def generate(
    session, *, text_model, image_model, count, output_root,
    selected_date=None, run_id=None, image_base_url=None, thumbnail_bucket=None,
):
    taxonomy = load_taxonomy(ROOT / "news_category.csv")
    publishers = load_publishers(ROOT / "publisher.csv")
    categories = [
        (category, subcategory)
        for category, subcategories in taxonomy.items()
        for subcategory in (subcategories or [None])
    ]
    selected_date = selected_date or article_timestamp().date()
    out = output_root / selected_date.isoformat()
    (out / "images").mkdir(parents=True, exist_ok=True)
    data_path = out / f"articles-{selected_date.isoformat()}.jsonl"

    # 같은 날짜의 백업 갱신과 재시도 시 기사 재사용을 한 실행씩 처리합니다.
    with (output_root / ".articles.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        articles = {}
        run_articles = {}
        saved_article_ids = set()
        # 날짜가 바뀌어도 보관된 일별 백업 전체에서 기사 수를 이어 셉니다.
        for backup in output_root.glob("*/articles-????-??-??.jsonl"):
            with backup.open(encoding="utf-8") as stream:
                for line in stream:
                    if line.strip():
                        saved_article_ids.add(json.loads(line)["id"])
        if data_path.exists():
            with data_path.open(encoding="utf-8") as stream:
                for line in stream:
                    if line.strip():
                        article = json.loads(line)
                        articles[article["id"]] = article
                        generation = article.get("generation") or {}
                        if run_id and generation.get("run_id") == run_id:
                            run_articles[generation.get("index")] = article

        for index in range(1, count + 1):
            article = run_articles.get(index)
            if article is None:
                article_id = "news-" + uuid.uuid7().hex
                category, subcategory = random.choice(categories)
                published_at = article_timestamp()
                draft = generate_article(session, text_model, category, subcategory, published_at)
                image_path = None
                if (len(saved_article_ids) + 1) % 10 == 0:
                    image_path = f"images/{article_id}.png"
                    save_thumbnail(session, image_model, draft.image_prompt, out / image_path)
                article = {
                    **draft.model_dump(exclude={"image_prompt"}),
                    "id": article_id,
                    "category": category,
                    "subcategory": subcategory,
                    "published_at": published_at.isoformat(timespec="seconds"),
                    "generated_at": article_timestamp().isoformat(timespec="seconds"),
                    "author": "가상뉴스 편집팀",
                    "publisher": random.choice(publishers),
                    "language": "ko-KR",
                    "is_synthetic": True,
                    "image_path": image_path,
                    "image_caption": (
                        "AI 생성 실사풍 이미지 · 실제 사건 사진이 아닙니다."
                        if image_path else None
                    ),
                }
                if run_id:
                    article["generation"] = {"run_id": run_id, "index": index}
                if image_base_url is not None:
                    article["image_url"] = resolve_image_url(article, data_path, output_root, image_base_url)
                articles[article_id] = article
                save_articles(data_path, articles.values())
                saved_article_ids.add(article_id)

            # 백업 이후 업로드해, 실패한 재시도에서도 같은 기사·PNG를 재사용합니다.
            if thumbnail_bucket and article.get("image_path"):
                upload_thumbnail(out / article["image_path"], output_root, thumbnail_bucket)

            if image_base_url is not None:
                if not article.get("image_url"):
                    article["image_url"] = resolve_image_url(article, data_path, output_root, image_base_url)
                    save_articles(data_path, articles.values())
                row = article_row(article, data_path, output_root, image_base_url)
                with psycopg.connect(connect_timeout=10) as connection:
                    with connection.cursor() as cursor:
                        upsert_articles(cursor, [row])

    return data_path


def read_secret(resource_name):
    """Workload Identity 등의 ADC 인증으로 Secret Manager 값을 읽습니다."""
    from google.api_core.exceptions import GoogleAPIError
    from google.auth.exceptions import DefaultCredentialsError
    from google.cloud import secretmanager

    try:
        with secretmanager.SecretManagerServiceClient() as client:
            secret = client.access_secret_version(request={"name": resource_name})
            return secret.payload.data.decode("utf-8")
    except (GoogleAPIError, DefaultCredentialsError, UnicodeDecodeError):
        raise ValueError("Secret Manager에서 값을 읽지 못했습니다. 실행 계정과 권한을 확인하세요.") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--text-model", required=True, help="JSON Schema를 지원하는 OpenRouter 모델 ID")
    parser.add_argument("--image-model", required=True, help="OpenRouter Images API 모델 ID")
    parser.add_argument("--count", type=int, default=1)
    parser.add_argument("--thumbnail-bucket", default=os.getenv("THUMBNAIL_BUCKET"),
                        help="썸네일 PNG를 업로드할 GCS 버킷. JSONL은 출력 폴더에 보관")
    parser.add_argument("--output-root", type=Path, default=ROOT / "output_with_thumbnail")
    parser.add_argument("--write-db", action="store_true", help="생성한 기사를 PostgreSQL에도 적재")
    parser.add_argument("--image-base-url", default=os.getenv("IMAGE_BASE_URL"),
                        help="배치 출력 폴더를 제공하는 이미지 서비스 URL")
    parser.add_argument("--date", type=date.fromisoformat, help="백업 폴더 날짜")
    parser.add_argument("--run-id", help="재시도에서도 유지되는 배치 실행 ID")
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count는 1 이상이어야 합니다.")
    if args.write_db:
        if not (args.date and args.run_id and args.image_base_url):
            parser.error("--write-db에는 --date, --run-id, 이미지 서비스 URL이 필요합니다.")
        missing = [name for name in ("PGHOST", "PGPORT", "PGDATABASE", "PGUSER") if not os.getenv(name)]
        if missing:
            parser.error("DB 환경변수를 설정하세요: " + ", ".join(missing))

    try:
        api_key = os.environ.get("OPENROUTER_API_KEY", "").strip()
        if os.environ.get("OPENROUTER_API_KEY_SECRET"):
            api_key = read_secret(os.environ["OPENROUTER_API_KEY_SECRET"]).strip()
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY 또는 OPENROUTER_API_KEY_SECRET을 설정하세요.")
        if args.write_db and os.environ.get("PGPASSWORD_SECRET"):
            os.environ["PGPASSWORD"] = read_secret(os.environ["PGPASSWORD_SECRET"])
        image_base_url = validate_image_base_url(args.image_base_url) if args.write_db else None
        with requests.Session() as session:
            session.headers["Authorization"] = f"Bearer {api_key}"
            path = generate(session, text_model=args.text_model, image_model=args.image_model,
                            count=args.count, output_root=args.output_root,
                            selected_date=args.date, run_id=args.run_id,
                            image_base_url=image_base_url, thumbnail_bucket=args.thumbnail_bucket)
    except ValidationError:
        parser.exit(1, "OpenRouter 기사 응답이 기사 스키마와 일치하지 않습니다.\n")
    except (requests.RequestException, psycopg.Error, OSError, ValueError) as error:
        parser.exit(1, f"뉴스 생성 실패: {error}\n")
    print(f"기사 {args.count}건 저장: {path}")


if __name__ == "__main__":
    main()
