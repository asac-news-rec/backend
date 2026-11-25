"""추론 서버(POST /v1/rank) 호출. 실패하면 None을 돌려주고 피드는 최신순을 그대로 쓴다."""
import logging
import math
import os

import requests

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 0.5  # 연결과 읽기에 각각 적용된다(전체 상한이 아니다)


def inference_url() -> str:
    """비어 있으면 추론 서버를 쓰지 않는다."""
    return os.environ.get("INFERENCE_URL", "").strip().rstrip("/")


def request_rank(url: str, request_id: str, reader_id: str, article_ids: list[str],
                 served_at: str) -> dict | None:
    try:
        response = requests.post(
            f"{url}/v1/rank",
            json={
                "request_id": request_id,
                "reader_id": reader_id,
                "candidates": article_ids,
                "context": {"request_time": served_at},
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()
        ranked_ids = [item["article_id"] for item in body["ranked"]]
        if len(set(ranked_ids)) != len(ranked_ids) or not set(ranked_ids) <= set(article_ids):
            raise ValueError("ranked에 중복이나 보내지 않은 기사가 있다")
        if [item["rank"] for item in body["ranked"]] != list(range(1, len(ranked_ids) + 1)):
            raise ValueError("ranked가 rank 순서가 아니다")
        for item in body["ranked"]:
            pctr = item["pctr"]
            if isinstance(pctr, bool) or not isinstance(pctr, (int, float)):
                raise ValueError("pctr이 숫자가 아니다")
            item["pctr"] = float(pctr)
            if not math.isfinite(item["pctr"]):
                raise ValueError("pctr이 유한한 수가 아니다")
        if not isinstance(body["model_version"], str):
            raise ValueError("model_version이 문자열이 아니다")
        return body
    except (requests.RequestException, ValueError, KeyError, TypeError, OverflowError) as exc:
        logger.warning("추론 서버 호출 실패, 최신순으로 대신한다: %s", exc)
        return None


def rerank(items: list[dict], request_id: str, reader_id: str, served_at: str) -> list[dict]:
    """한 페이지 안에서 순서를 바꾸고 반환 기록용 score·model_version을 붙인다.

    추론 서버의 features_as_of는 아직 요청 시각을 그대로 돌려주는 임시값이라 저장하지 않는다.
    """
    url = inference_url()
    result = None
    if url and items:
        result = request_rank(
            url, request_id, reader_id, [item["article_id"] for item in items], served_at,
        )
    if result is None:
        version = "fallback" if url else None
        return [dict(item, score=None, model_version=version, features_as_of=None)
                for item in items]

    scores = {item["article_id"]: item["pctr"] for item in result["ranked"]}
    order = {item["article_id"]: index for index, item in enumerate(result["ranked"])}
    # sorted는 안정 정렬이라 점수가 없는 기사는 뒤에서 최신순을 유지한다.
    return [
        dict(item, score=scores.get(item["article_id"]), model_version=result["model_version"],
             features_as_of=None)
        for item in sorted(items, key=lambda item: order.get(item["article_id"], len(order)))
    ]
