import json
from pathlib import Path


PENDING_DIR = Path("/var/spool/news-logs/pending")


def prepare_log_directory() -> Path:
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    return PENDING_DIR


def write_feed_log(reader_id: str, response: dict) -> None:
    """최종 응답에 포함된 기사별 반환 로그를 전송 대기 폴더에 저장한다."""
    items = response["items"]
    if not items:
        return

    pending_dir = prepare_log_directory()
    request_id = response["request_id"]
    jsonl_path = pending_dir / f"feed-{request_id}.jsonl"
    metadata_path = pending_dir / f"feed-{request_id}.meta.json"
    jsonl_tmp = jsonl_path.with_suffix(".jsonl.tmp")
    metadata_tmp = metadata_path.with_suffix(".json.tmp")

    with jsonl_tmp.open("w", encoding="utf-8") as log_file:
        for item in items:
            record = {
                "request_id": request_id,
                "impression_id": item["impression_id"],
                "reader_id": reader_id,
                "article_id": item["article_id"],
                "position": item["position"],
                "served_at": response["served_at"],
            }
            log_file.write(json.dumps(record, ensure_ascii=False) + "\n")

    metadata = {"request_id": request_id, "expected_item_count": len(items)}
    metadata_tmp.write_text(json.dumps(metadata) + "\n", encoding="utf-8")
    metadata_tmp.replace(metadata_path)
    # JSONL이 보이는 시점에는 메타데이터도 읽을 수 있어야 한다.
    jsonl_tmp.replace(jsonl_path)
