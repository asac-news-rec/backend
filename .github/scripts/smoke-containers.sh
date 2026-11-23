#!/usr/bin/env bash
# FastAPI 이미지의 기동과 OpenAPI 응답을 DB 연결 없이 검사합니다.
set -euo pipefail

if (( $# != 1 )); then
  echo "사용법: bash .github/scripts/smoke-containers.sh <FastAPI 이미지>" >&2
  exit 2
fi

was_image="$1"
container_id=""
schema_file="$(mktemp "${RUNNER_TEMP:-${TMPDIR:-/tmp}}/news-openapi.XXXXXX")"

cleanup() {
  local exit_status=$?
  if [[ -n "$container_id" ]]; then
    if (( exit_status != 0 )); then
      docker logs "$container_id" || true
    fi
    docker rm -f "$container_id" >/dev/null 2>&1 || true
  fi
  rm -f "$schema_file"
}
trap cleanup EXIT

# 컨테이너의 8000번 포트를 실행기의 임의 포트에 연결합니다.
container_id="$(docker run --detach --platform linux/amd64 \
  --publish 127.0.0.1::8000 "$was_image")"
api_address="$(docker port "$container_id" 8000/tcp)"

# Nginx를 거치지 않으므로 /api 접두사 없이 직접 조회합니다.
http_status="$(curl --fail --silent --show-error \
  --retry 15 --retry-delay 1 --retry-all-errors --retry-max-time 25 --max-time 5 \
  --output "$schema_file" --write-out '%{http_code}' \
  "http://$api_address/openapi.json")"
if [[ "$http_status" != 200 ]]; then
  echo "FastAPI HTTP 200 응답이 필요하지만 $http_status 상태를 받았습니다." >&2
  exit 1
fi
jq --exit-status '.paths["/v1/news/feed"].post | type == "object"' "$schema_file" >/dev/null
echo "FastAPI 기동·OpenAPI·피드 경로 검사 통과"
