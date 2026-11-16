# import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import os
from typing import Annotated
from uuid import uuid7
from pydantic import AwareDatetime, BaseModel, Field, field_serializer
from .repository import ArticleNotFound, fetch_news, set_like, fetch_big_category, fetch_sub_category

import psycopg
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from itsdangerous import BadData, URLSafeTimedSerializer
from psycopg_pool import PoolTimeout
from .db import connect, database_pool
# 반환 로그 구현은 루트 logging/에 보관합니다. 아래는 기존 연결 코드입니다.
# from .logging.feed_log import prepare_log_directory, write_feed_log

# logger = logging.getLogger(__name__)


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     try:
#         prepare_log_directory()
#     except OSError:
#         logger.exception("뉴스 로그 대기 폴더 준비 실패")
#     yield

@asynccontextmanager
async def lifespan(_app: FastAPI):
    with database_pool():
        yield


# root_path는 외부에서 /api 접두사를 통해 접근한다는 정보
app = FastAPI(root_path="/api", lifespan=lifespan)


@app.exception_handler(PoolTimeout)
async def handle_pool_timeout(_request: Request, _exc: PoolTimeout) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": "DB 연결을 기다리는 시간이 초과되었습니다."},
    )

READER_COOKIE = "news_reader"
READER_MAX_AGE = 30 * 24 * 60 * 60


def reader_signer() -> URLSafeTimedSerializer:
    secret = os.environ.get("READER_COOKIE_SECRET")
    if not secret:
        raise HTTPException(status_code=503, detail="익명 독자 인증을 사용할 수 없습니다.")
    return URLSafeTimedSerializer(secret, salt="news-reader-v1")


def read_reader_id(token: str | None) -> str | None:
    if not token:
        return None
    try:
        reader_id = reader_signer().loads(token, max_age=READER_MAX_AGE)
    except BadData:
        return None
    return reader_id if isinstance(reader_id, str) and reader_id else None


def require_reader_id(
    token: Annotated[str | None, Cookie(alias=READER_COOKIE)] = None,
) -> str:
    reader_id = read_reader_id(token)
    if reader_id is None:
        raise HTTPException(status_code=401, detail="익명 독자 인증이 필요합니다.")
    return reader_id


class FeedCursor(BaseModel):
    published_at: AwareDatetime
    article_id: str = Field(min_length=1)
    returned_count: int = Field(ge=1)


class FeedRequest(BaseModel):
    category: str | None = None
    subcategory: str | None = None
    cursor: FeedCursor | None = None


class FeedItem(BaseModel):
    article_id: str
    title: str
    subtitle: str | None
    summary: str | None
    paragraphs: list[str]
    tags: list[str]
    category: str
    subcategory: str | None
    published_at: datetime = Field(json_schema_extra={"format": "date-time"})
    author: str | None
    publisher: str | None
    language: str | None
    is_synthetic: bool
    url: str | None
    image_url: str | None
    image_caption: str | None
    is_liked: bool
    impression_id: str
    position: int

    @field_serializer("published_at", when_used="json")
    def serialize_published_at(self, value: datetime) -> str:
        # 기존 JSON의 시간대 표기(+00:00 등)를 유지한다.
        return value.isoformat()


class FeedResponse(BaseModel):
    request_id: str
    served_at: str = Field(json_schema_extra={"format": "date-time"})
    items: list[FeedItem]
    next_cursor: FeedCursor | None


class CategoryResponse(BaseModel):
    category_list: list[str]


class SubcategoryRequest(BaseModel):
    category: str = Field(min_length=1)


class SubcategoryResponse(BaseModel):
    sub_category_list: list[str]


@app.get("/health")
def health():
    # psycopg.Error 오류가 발생하는 지가 성공/실패의 기준. db접속 및 결과조희의 성공/실패를 포함
    try:
        # 풀에서 빌린 연결은 트랜잭션 종료 후 반환한다.
        with connect() as conn:
            result = conn.execute("SELECT 1 AS ok").fetchone()
        return {
            "status":"ok",
            "database":result['ok']
        }
    except psycopg.Error as exc:
        # HTTPException : 현재 처리를 중단하고 client에 HTTP오류응답을 보내는 code
        raise HTTPException(
            status_code = 503,
            detail="DB연결 또는 query실행에 실패하였습니다."
            # from exc: “새로 발생시키는 예외의 원인이 원래 오류 exc다”라고 연결하는 문법
        ) from exc
    
@app.post("/news/feed", response_model=FeedResponse)
def news_feed(
    body: FeedRequest,
    reader_id: Annotated[str, Depends(require_reader_id)],
):
    after = None
    returned_count = 0
    if body.cursor is not None:
        after = (body.cursor.published_at, body.cursor.article_id)
        returned_count = body.cursor.returned_count

    try:
        with connect() as conn:
            items, has_more = fetch_news(
                conn,
                reader_id,
                category=body.category,
                subcategory=body.subcategory,
                after=after,
            )
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="뉴스조회에 실패하였습니다.",
        ) from exc

    for position, item in enumerate(items, start=returned_count + 1):
        item["impression_id"] = str(uuid7())
        item["position"] = position

    next_cursor = None
    if has_more:
        # 실제 응답에 포함된 마지막 기사부터 다음 페이지를 이어 간다.
        last_item = items[-1]
        next_cursor = FeedCursor(
            published_at=last_item["published_at"],
            article_id=last_item["article_id"],
            returned_count=returned_count + len(items),
        )

    response = {
        "request_id": str(uuid7()),
        "served_at": datetime.now(timezone.utc).isoformat(),
        "items": items,
        "next_cursor": next_cursor,
    }
    # 반환 로그 파일 기록은 후속 배포에서 연결합니다.
    # try:
    #     write_feed_log(reader_id, response)
    # except OSError:
    #     logger.exception("뉴스 반환 로그 저장 실패: request_id=%s", response["request_id"])
    return response


# 설정·해제 API가 공통으로 사용하는 처리 함수
def change_like(article_id: str, reader_id: str, desired: bool):
    try:
        with connect() as conn:
            result = set_like(
                conn,
                reader_id,
                article_id,
                desired,
            )

        # with 블록 종료 시 DB 커밋에 성공한 뒤 응답
        return result

    except ArticleNotFound as exc:
        raise HTTPException(
            status_code=404,
            detail="기사가 없습니다.",
        ) from exc

    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="좋아요 변경에 실패했습니다.",
        ) from exc


@app.put("/news/{article_id}/like")
def like(article_id: str, reader_id: Annotated[str, Depends(require_reader_id)]):
    return change_like(article_id, reader_id, True)


@app.delete("/news/{article_id}/like")
def unlike(article_id: str, reader_id: Annotated[str, Depends(require_reader_id)]):
    return change_like(article_id, reader_id, False)


@app.post("/user/anonymous")
def create_anonymous_user(
    response: Response,
    token: Annotated[str | None, Cookie(alias=READER_COOKIE)] = None,
):
    reader_id = read_reader_id(token)
    if reader_id is None:
        reader_id = str(uuid7())
        response.set_cookie(
            key=READER_COOKIE,
            value=reader_signer().dumps(reader_id),
            max_age=READER_MAX_AGE,
            httponly=True,
            secure=os.environ.get("READER_COOKIE_SECURE", "true").lower() != "false",
            samesite="lax",
            path="/",
        )

    response.headers["Cache-Control"] = "no-store"
    return {"reader_id": reader_id}


@app.post("/category", response_model=CategoryResponse)
def call_category():
    try:
        with connect() as conn:
            rows = fetch_big_category(conn)
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="카테고리 조회에 실패했습니다.",
        ) from exc
    return {"category_list": [row["category"] for row in rows]}


@app.post("/subcategory", response_model=SubcategoryResponse)
def call_subcategory(body: SubcategoryRequest):
    try:
        with connect() as conn:
            rows = fetch_sub_category(conn, body.category)
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="소분류 조회에 실패했습니다.",
        ) from exc
    return {"sub_category_list": [row["subcategory"] for row in rows]}
