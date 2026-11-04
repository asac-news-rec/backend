from datetime import datetime, timezone
from uuid import uuid7
from pydantic import BaseModel,Field
from .repository import ArticleNotFound, fetch_news, set_like

import psycopg
from fastapi import FastAPI,HTTPException
from .db import connect

app = FastAPI()

# 뉴스조회 요청 json의 형식
class FeedRequest(BaseModel):
    reader_id:str = Field(min_length=1, max_length=128)
    offset:int = Field(default = 0,ge=0)
class LikeRequest(BaseModel):
    reader_id: str = Field(min_length=1, max_length=128)

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
            items, has_more = fetch_news(conn,body.reader_id,body.offset)
        # 각 기사에 이번 노출의 식별자와 표시 순서 추가
        for position, item in enumerate(items,start=body.offset + 1):
            item['impression_id'] = str(uuid7())
            item['position'] = position
        next_offset = (
            body.offset+len(items)
            if has_more else None
        )
        return {
            "reader_id": body.reader_id,
            "request_id":str(uuid7()),
            "served_at":datetime.now(timezone.utc).isoformat(),
            "items":items,
            "next_offset":next_offset
        }
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