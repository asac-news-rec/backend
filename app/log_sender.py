import json
import logging
import os
import time
from pathlib import Path

import requests

from .feed_log import PENDING_DIR

logger = logging.getLogger(__name__)
POLL_INTERVAL_SECONDS = 10
REJECTED_DIR = PENDING_DIR.parent / "rejected"


def send_file(session: requests.Session, receiver_url: str, jsonl_path: Path) -> None:
    metadata_path = jsonl_path.with_suffix(".meta.json")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    with jsonl_path.open("rb") as log_file:
        response = session.post(
            receiver_url,
            files={"file": (jsonl_path.name, log_file, "application/x-ndjson")},
            data={
                "request_id": metadata["request_id"],
                "expected_item_count": str(metadata["expected_item_count"]),
            },
            timeout=5,
            allow_redirects=False,
        )

    if response.status_code == 200:
        jsonl_path.unlink()
        metadata_path.unlink()
    elif response.status_code in (400, 422):
        REJECTED_DIR.mkdir(parents=True, exist_ok=True)
        jsonl_path.replace(REJECTED_DIR / jsonl_path.name)
        metadata_path.replace(REJECTED_DIR / metadata_path.name)
        logger.error("로그 파일 검증 거절: %s (HTTP %s)", jsonl_path.name, response.status_code)
    else:
        logger.warning("로그 전송 실패: %s (HTTP %s)", jsonl_path.name, response.status_code)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    receiver_url = os.environ.get("LOG_RECEIVER_URL", "").strip()
    if not receiver_url:
        raise SystemExit("LOG_RECEIVER_URL에 로그 수신 API 주소를 설정하세요.")

    with requests.Session() as session:
        while True:
            for jsonl_path in sorted(PENDING_DIR.glob("feed-*.jsonl")):
                try:
                    send_file(session, receiver_url, jsonl_path)
                except (requests.RequestException, OSError, ValueError, KeyError):
                    logger.exception("대기 파일 처리 실패: %s", jsonl_path.name)
            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
