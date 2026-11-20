#!/usr/bin/env bash
set -euo pipefail

was_image="$1"
nginx_image="$2"
fastapi_container=news-fastapi-smoke
nginx_container=news-nginx-smoke
schema_file="$RUNNER_TEMP/news-openapi.json"

cleanup() {
  local exit_status=$?
  if (( exit_status != 0 )); then
    docker logs "$fastapi_container" || true
    docker logs "$nginx_container" || true
  fi
  docker rm -f "$nginx_container" "$fastapi_container" >/dev/null 2>&1 || true
}
trap cleanup EXIT

# FastAPI의 네트워크를 Nginx와 공유한다. 실행기에는 Nginx의 80번 포트만 연다.
docker run --detach --platform linux/amd64 --name "$fastapi_container" --publish 127.0.0.1::80 "$was_image"
docker run --detach --platform linux/amd64 --name "$nginx_container" --network "container:$fastapi_container" "$nginx_image"

# 배포용 Nginx가 /api/ 요청을 FastAPI로 전달하는지 DB 연결 없이 확인한다.
# Nginx에 접속할 주소를 알아냄
nginx_address="$(docker port "$fastapi_container" 80/tcp)"
# Nginx를 거쳐 FastAPI의 명세를 받아옵니다.curl이 **`GET /api/openapi.json`**을 Nginx에 보냅니다
http_status="$(curl --fail --silent --show-error \
  --retry 15 --retry-delay 1 --retry-all-errors --retry-max-time 25 --max-time 5 \
  --output "$schema_file" --write-out '%{http_code}' \
  "http://$nginx_address/api/openapi.json")"
if [[ "$http_status" != 200 ]]; then
  echo "Expected HTTP 200 from Nginx, got $http_status" >&2
  exit 1
fi
jq --exit-status '.paths["/v1/news/feed"].post | type == "object"' "$schema_file" >/dev/null
echo "Nginx forwarded the API request to FastAPI."
