import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import uuid7
from pydantic import BaseModel,Field
from .repository import ArticleNotFound, fetch_news, set_like, fetch_big_category, fetch_sub_category

import psycopg
from fastapi import FastAPI,HTTPException
from .db import connect
from .feed_log import prepare_log_directory, write_feed_log

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        prepare_log_directory()
    except OSError:
        logger.exception("뉴스 로그 대기 폴더 준비 실패")
    yield

# root_path는 외부에서 /api 접두사를 통해 접근한다는 정보
app = FastAPI(root_path="/api", lifespan=lifespan)

# 뉴스조회 요청 json의 형식
class FeedRequest(BaseModel):
    reader_id:str = Field(min_length=1, max_length=128)
    offset:int = Field(default = 0,ge=0)
    category:str | None = None
    subcategory:str | None = None
class LikeRequest(BaseModel):
    reader_id: str = Field(min_length=1, max_length=128)

class SubcategoryRequest(BaseModel):
    category: str = Field(min_length=1)

@app.get("/health")
def health():
    # psycopg.Error 오류가 발생하는 지가 성공/실패의 기준. db접속 및 결과조희의 성공/실패를 포함
    try:
        # 시작:connect()로 접속 -> tr커밋 후 연결 종료(정상 or 오류)
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
    
@app.post("/news/feed")
def news_feed(body:FeedRequest):
    try:
        # DB연결 후 해당 사용자의 뉴스 목록 조회
        with connect() as conn:
            items, has_more = fetch_news(
                conn,body.reader_id,
                body.offset,
                category = body.category,
                subcategory=body.subcategory,
                )
        # 각 기사에 이번 노출의 식별자와 표시 순서 추가
        for position, item in enumerate(items,start=body.offset + 1):
            item['impression_id'] = str(uuid7())
            item['position'] = position
        next_offset = (
            body.offset+len(items)
            if has_more else None
        )
        response = {
            "request_id":str(uuid7()),
            "served_at":datetime.now(timezone.utc).isoformat(),
            "items":items,
            "next_offset":next_offset,
        }
        try:
            write_feed_log(body.reader_id, response)
        except OSError:
            logger.exception("뉴스 반환 로그 저장 실패: request_id=%s", response["request_id"])
        return response
    except psycopg.Error as exc:
        raise HTTPException(
            status_code=503,
            detail="뉴스조회에 실패하였습니다."
        ) from exc
    
# 설정·해제 API가 공통으로 사용하는 처리 함수
def change_like(article_id, body, desired):
    try:
        with connect() as conn:
            result = set_like(
                conn,
                body.reader_id,
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
def like(article_id: str, body: LikeRequest):
    return change_like(article_id, body, True)


@app.delete("/news/{article_id}/like")
def unlike(article_id: str, body: LikeRequest):
    return change_like(article_id, body, False)

@app.post("/user/anonymous")
def create_anonymous_user():
    return {
        "reader_id":str(uuid7())
    }

@app.post("/category")
def call_category():
    with connect() as conn:
        rows = fetch_big_category(conn)
    return {
            "category_list" : [row['category'] for row in rows]
        } 
@app.post("/subcategory")
def call_subcategory(body: SubcategoryRequest):
    with connect() as conn:
        rows = fetch_sub_category(conn,body.category)
    return {'sub_category_list' : [row['subcategory'] for row in rows] }
