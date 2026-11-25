# 뉴스 추천 백엔드

ASAC 뉴스 추천 시스템의 FastAPI 서버입니다. 뉴스 피드와 카테고리를 조회하고, 익명 독자 ID를 발급하며, 좋아요 상태와 변경 이력을 PostgreSQL에 기록합니다. 기사·썸네일 생성 및 기사 적재 도구도 이 저장소에서 관리합니다.

## 저장소 구성

| 위치 | 역할 |
| --- | --- |
| [`app/`](app/) | FastAPI 라우트, PostgreSQL 연결·쿼리 |
| [`compose.yaml`](compose.yaml) | 로컬 PostgreSQL 18·FastAPI 실행 구성 |
| [`Dockerfile`](Dockerfile) | FastAPI 이미지 빌드 |
| [`tests/`](tests/) · [`pytest.ini`](pytest.ini) | API 테스트와 PostgreSQL 조회 통합 테스트 |
| [`pyproject.toml`](pyproject.toml) · [`uv.lock`](uv.lock) | Python 3.14 의존성과 생성·테스트 그룹, 고정된 패키지 버전 |
| [`generate/`](generate/) · [`exports/`](exports/) | 기사·썸네일 생성, 기사 적재, DB 백업과 복원 |
| [`.github/workflows/`](.github/workflows/) | PR 브랜치 이름 검사, 백엔드 CI, Cloud Run CD |

## 로컬 실행

### PostgreSQL과 FastAPI 실행

Docker와 Docker Compose가 필요합니다. 아래 명령은 `backend` 루트에서 실행합니다. 화면 제공용 Nginx 이미지의 빌드·배포는 프론트 저장소에서 관리합니다.

처음 설정할 때 [`.env.example`](.env.example)을 `.env`로 복사하고 로컬 DB 접속값을 채웁니다. `PGPASSWORD`를 포함한 실제 접속값은 로컬 `.env`에 보관합니다.

```bash
docker compose config --quiet
docker compose up -d --build --wait --wait-timeout 90
docker compose ps
```

| 접속 대상 | 기본 주소 |
| --- | --- |
| API 문서 | <http://127.0.0.1:8000/docs> |
| API 상태와 DB 접속 확인 | <http://127.0.0.1:8000/health> |
| 로컬 PostgreSQL | `127.0.0.1:5433` · 기본 DB `newsdb`, 사용자 `recommend` |

`DB_POOL_MAX_SIZE`는 FastAPI 프로세스당 최대 PostgreSQL 연결 수입니다.
로컬에서는 `.env`에서 조정하며 기본값은 `4`입니다. 풀은 DB 요청이 들어오면
연결을 만들고 이후 요청에 재사용합니다. 연결을 3초 안에 얻지 못한 요청은 HTTP 503을 받습니다.

로컬에서는 FastAPI의 8000번 포트에 직접 요청합니다(`POST /v1/news/feed`). Cloud Run의 기존 Nginx를 거치는 외부 경로는 `POST /api/v1/news/feed`입니다.
이전 Nginx 구성은 [삭제 전 커밋의 파일](https://github.com/asac-news-rec/backend/tree/54317e07df0dc8076c2949f8d66d0368bbdd4af6/nginx)에서 확인합니다.
Git에서 제외된 작성자 PC의 보관본은 새 checkout의 실행 전제에 포함하지 않습니다.

### 로컬 화면·썸네일 연동

**[현재 코드]** 백엔드 Compose는 Nginx를 실행하지 않으므로 이전 로컬 8080 포트와
`/images/` 경로를 제공하지 않습니다. 주석 처리된 Nginx 블록은 삭제된 설정 파일을
참조하므로 주석만 해제해도 복원되지 않습니다.
[프론트 Compose](https://github.com/asac-news-rec/frontend/blob/150a11881ee327518ec18c8fdc8ece295dfffebc/compose.yaml)는
Nginx 대신 Node 개발 서버를 실행합니다. 화면 기본 주소는 `http://127.0.0.1:4181`이며,
기본 API 연결 대상 `http://host.docker.internal:8080/`은 이전 백엔드 Nginx를 전제로 합니다.

현재 프론트 개발 서버로 연결하려면, 백엔드를 먼저 실행한 뒤 `backend` 루트에서
다음처럼 API 연결 대상만 지정할 수 있습니다. 옆에 `frontend` 저장소가 있어야 합니다.
이 연결은 코드 기준 안내이며 이번 문서 수정에서 화면 통합 실행을 검증하지 않았습니다.

```bash
NEWS_BACKEND_URL=http://host.docker.internal:8000/ docker compose -f ../frontend/compose.yaml up -d --build web
```

썸네일은 DB의 `image_url`이 가리키는 실제 서버에서 제공되어야 합니다.
GCS URL을 사용하는 기사는 해당 객체 접근 권한을 확인합니다. 로컬 파일을 사용하는
백업은 이미지 폴더도 별도로 전달받고, 저장된 URL의 호스트·포트·경로에 맞춰
제공해야 합니다. `http://localhost:8001/...` URL의 실행 예시는
[백업 이미지 확인 절](exports/README.md#6-이미지-확인)을 참고합니다.
`/images/...` 상대 URL은 현재 백엔드 Compose만으로 제공되지 않습니다.

**[계획·프론트 협의 필요]** 프론트에서 로컬 Nginx를 `127.0.0.1:8080:80`으로
실행하고 API 프록시와 `/images/` 마운트를 구성하면 기존 8080 연결 대상을 유지할 수
있습니다. 별도 로컬 컨테이너의 프록시는 공용 Docker 네트워크의 API 서비스 주소나
`host.docker.internal:8000`을 사용해야 합니다. Cloud Run의 같은 인스턴스에서 쓰는
`127.0.0.1:8000`을 별도 로컬 Nginx 컨테이너에 그대로 복사하지 않습니다.
이 로컬 구성은 아직 구현된 것으로 간주하지 않습니다. 운영 Cloud Run의 80→8000
연결은 이번 로컬 8080 포트 변경과 무관합니다.

### FastAPI를 직접 실행

백엔드 코드를 로컬에서 수정하며 확인할 때는 PostgreSQL만 Compose로 띄우고 `uv`로 FastAPI를 실행합니다. FastAPI는 표준 라이브러리의 `uuid7()`을 사용하므로 Python 3.14가 필요합니다.

```bash
docker compose up -d --wait postgres
uv python install 3.14
uv sync --locked --no-install-project
uv run --no-sync python -m uvicorn app.main:app --reload
```

직접 실행한 FastAPI의 상태 확인 주소는 <http://127.0.0.1:8000/health>입니다.

## 기사 적재와 DB 관리

Compose로 PostgreSQL을 시작하면 DB와 계정이 준비됩니다. **기사·좋아요 테이블과 기사 데이터는 적재 단계에서 준비**합니다. 적재기는 백엔드 루트의 `.env`에서 DB 접속값을 읽습니다.

```bash
uv sync --locked --group generation --no-install-project
(cd generate && ../.venv/bin/python -m load_postgres --output-root local_generate/output_with_thumbnail --date 2026-11-02 --validate-only)
(cd generate && ../.venv/bin/python -m load_postgres --output-root local_generate/output_with_thumbnail --date 2026-11-02)
```

날짜는 적재할 데이터 폴더에 맞게 바꿉니다. 위 `local_generate/output_with_thumbnail`은 별도로 준비한 데이터 폴더 예시이며 새 clone에 포함되지 않습니다. 먼저 `--validate-only`로 JSONL을 검증하고 통과한 뒤 실제 적재 명령을 실행합니다. 현재 생성기와 썸네일 업로드 설정은 [생성기 안내](generate/README.md), 기존 DB 백업과 로컬 이미지를 받을 때는 [백업 복원 안내](exports/README.md)를 참고하세요.

### 피드 반환 로그 테이블 준비

기사·좋아요 테이블 외에 `public.news_impressions` 테이블도 필요합니다.
기사 적재기의 `ensure_schema()`는 이 로그 테이블을 만들지 않습니다.
운영 Cloud SQL은 코드 배포 전에 인프라 담당자에게 로그 테이블 생성과 현재
FastAPI의 PostgreSQL 접속 사용자의 `INSERT` 권한 부여를 요청합니다.
로컬 DB에도 동일한 구조의 로그 테이블이 필요하며, 테스트 DB는
`tests/conftest.py`에서 테스트용 테이블을 준비합니다.
현재 CI/CD는 운영 테이블 생성과 권한 부여를 자동 실행하지 않습니다.

`POST /v1/news/feed`는 반환 기사마다 같은 응답의 ID·순서·시각을 사용해
로그를 저장합니다. `INFERENCE_URL`이 비어 있으면 최신순으로 응답하고
`score`, `model_version`, `features_as_of`는 `NULL`입니다. `INFERENCE_URL`이 있으면
추론 서버 `POST /v1/rank`(연결·읽기 타임아웃 각각 0.5초)로 한 페이지 안의 순서를 바꾸고 `score`와
`model_version`을 저장합니다. 호출에 실패하면 최신순으로 응답하고 `model_version`은
`fallback`입니다. `features_as_of`는 추론 서버가 실제 피처 시각을 줄 때까지 `NULL`입니다.
다음 페이지 커서는 추천 순서가 아니라 최신순 기준입니다.
롤백은 `INFERENCE_URL`을 비웁니다.
저장과 커밋이 성공하면 피드를 반환하고, DB 오류가 발생하면 기사 목록 대신
HTTP 503과 `뉴스 전송내역 저장에 실패하였습니다.`를 반환합니다.
이 로그는 서버 반환 기록이며 브라우저의 실제 수신·화면 노출을 보장하지 않습니다.

이번 변경은 기존 DB의 저장 공간과 INSERT·인덱스 유지 비용을 늘리며 새 클라우드
리소스를 만들지 않습니다. 롤백은 로그 저장 연결 전의 백엔드 이미지로 되돌립니다.
기존 로그 테이블과 데이터는 보존하고, 삭제가 필요하면 별도로 결정합니다.

### 익명 독자 쿠키

브라우저는 먼저 `POST /api/v1/user/anonymous`를 호출해 `news_reader` 서명 쿠키를 받습니다.
유효한 쿠키가 있으면 같은 독자 ID를 반환합니다. 피드와 좋아요 API는 이 쿠키에서
검증한 `reader_id`를 사용하며, 쿠키가 없거나 만료됐으면 HTTP 401을 반환합니다.
쿠키는 발급 후 30일 동안 유효합니다. 기존 브라우저는 새 쿠키를 받을 때 새 익명 ID를 발급받습니다.

로컬에서는 `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'`로 키를 한 번 생성해
루트 `.env`의 `READER_COOKIE_SECRET`에 넣습니다. HTTP로 접속하는 로컬 환경에서는
`READER_COOKIE_SECURE=false`를 사용합니다.

### 카테고리 조회

`POST /category`는 `category_list`를 반환합니다.
`POST /subcategory`에 `{"category": "경제"}`를 보내면 해당 대분류의
소분류를 이름순으로 정렬해 `sub_category_list`로 반환합니다.
두 목록은 문자열 배열이며 OpenAPI에서 응답 형식을 확인할 수 있습니다.
두 API는 DB 연결 또는 쿼리 실행에 실패하면 HTTP 503을 반환합니다.

### 뉴스 피드 페이지 조회

`POST /v1/news/feed`의 첫 요청은 서명 쿠키와 필요한 카테고리 필터를 보냅니다.
필터를 생략할 경우 JSON 본문은 `{}`입니다.
다음 페이지가 있으면 응답의 `next_cursor`에 마지막 기사의 발행 시각과 ID,
지금까지 반환한 기사 수가 담깁니다. 같은 필터를 유지하고 이 객체를 다음 요청의
`cursor`에 그대로 넣습니다. `next_cursor`가 `null`이면 마지막 페이지입니다.
페이지당 최대 20건을 반환하며, `position`은 이전 페이지의 마지막 순번부터 이어집니다.

이 API 변경을 배포할 때는 프론트 API 클라이언트도 `cursor`와 `next_cursor`를 사용하고,
피드나 좋아요를 호출하기 전에 익명 독자 쿠키를 발급받아야 합니다.

로컬 PostgreSQL 데이터는 `asac-news-backend-postgres-data` 볼륨에 저장됩니다. 서비스만 멈출 때는 `docker compose stop`을 사용합니다. `docker compose down -v`는 DB 볼륨도 삭제합니다. 초기 DB 계정과 비밀번호는 빈 볼륨을 처음 시작할 때 적용됩니다.

## 검증

```bash
uv python install 3.14
uv sync --locked --group test --no-install-project
uv run --no-sync python -m pytest
docker compose config --quiet
git diff --check
```

뉴스 피드 정상 조회 테스트와 SQL 직접 조회 테스트는 fixture로 테스트용 임시 PostgreSQL에 기사를 넣고 조회한 뒤 롤백합니다. 피드의 DB 오류 응답은 `FakeConnection`으로 재현합니다.
기사 INSERT는 `tests/helpers.py`의 일반 함수 `insert_articles(conn, rows)`를
명시적으로 import해 호출합니다. `tests/conftest.py`는 DB 연결과 공용 테스트 준비를
관리하며, 기사 준비 코드가 연결과 기사 목록을 이 함수에 직접 전달합니다.
`tests/test_api.py`는 v1 피드 응답과 DB의 반환 로그가 일치하는지 확인합니다.
로그 저장 실패 시 503을 반환하는 검사는 저장 함수만 오류를 내도록 임시 교체합니다.
`tests/test_db_pool.py`는 테스트용 임시 PostgreSQL에서 연결 재사용, 풀 고갈과 반환 후 복구,
좋아요 설정·해제 시 상태와 이력의 커밋 및 이력 저장 실패 시 롤백을 검증합니다.

로컬에서 PostgreSQL 통합 테스트를 실행하려면 테스트용 임시 PostgreSQL의 접속 문자열을 `POSTGRES_TEST_DSN`으로 지정합니다. 지정하지 않으면 PostgreSQL을 사용하는 테스트를 건너뜁니다.

[백엔드 CI](.github/workflows/ci.yml)는 PR과 `main` 푸시에서 테스트 전용 PostgreSQL 18을 시작하고 `pytest`를 실행합니다. PR에서는 FastAPI 이미지 하나를 빌드해 [스모크 테스트](.github/scripts/smoke-containers.sh)를 실행합니다. 스크립트는 임시 컨테이너의 8000번 포트에서 `/openapi.json`의 HTTP 200과 `POST /v1/news/feed` 정의를 확인한 뒤 컨테이너와 임시 파일을 정리합니다. Nginx·화면 파일·DB 연결은 이 스크립트의 검사 대상이 아닙니다.

## Cloud Run 배포

[백엔드 CD](.github/workflows/cd.yml)는 GitHub에서 백엔드 릴리스를 공개하면 실행됩니다.

1. 릴리스 태그의 커밋이 `main` 푸시에서 CI를 통과했는지 확인합니다. 통과한 백엔드
   커밋을 가져옵니다.
2. FastAPI 이미지만 빌드하고 임시 컨테이너에서 스모크 테스트를 실행합니다.
3. Google Cloud에 인증하고 FastAPI 이미지를 Artifact Registry에 업로드합니다.
4. `gcloud run services update news-feed --container fastapi --image ...`로 해당 컨테이너 이미지 하나만 갱신합니다. 프로젝트·리전 등 서비스 옵션은 `--container` 앞에 지정합니다.

기존 Cloud Run 서비스 `news-feed`와 이름이 `fastapi`인 컨테이너가 준비되어 있어야 합니다.
서비스 전체 YAML을 생성하거나 교체하지 않습니다. 기존 Nginx 이미지, 포트, 실행 계정,
Cloud SQL 연결, 환경변수와 Secret 참조 등 기존 설정은 유지합니다.
프론트 저장소가 화면 파일을 포함한 `nginx` 이미지를 별도로 갱신합니다.
같은 인스턴스에서 Nginx는 80번 포트로 받고 `/api/` 요청을 FastAPI의
`127.0.0.1:8000`으로 전달합니다.
[프론트의 현재 Nginx 설정](https://github.com/asac-news-rec/frontend/blob/150a11881ee327518ec18c8fdc8ece295dfffebc/nginx/cloud-run.conf)에
`location /api/`와 `proxy_pass http://127.0.0.1:8000/`이 정의되어 있습니다.
이는 저장소 코드 확인 결과이며 실제 서비스에 해당 이미지가 배포되었는지는 별도 확인합니다.

### 최초 구성과 배포 순서

- 이번 CD는 기존 서비스 갱신용입니다. 신규 환경은 인프라 담당자와 서비스·실행 계정·
  Cloud SQL·Secret 설정을 준비하고 프론트·백엔드 담당자가 두 컨테이너 구성을 확인한
  뒤 사용합니다. 백엔드 배포자는 기존 `news-feed`에 `nginx`와 `fastapi`라는 이름의
  컨테이너가 있는지 확인합니다. 없거나 이름이 다르면 이 CD를 최초 구성용으로 실행하지 않습니다.
- 백엔드의 `concurrency`는 이 저장소 안의 배포만 직렬화합니다. 다른 저장소의 프론트
  배포까지 잠그지 않습니다. 같은 서비스의 동시 갱신 동작은 아직 실환경 검증하지
  않았으므로, 프론트·백엔드 담당자가 배포 시간을 조율해 한쪽 완료 후 다른 쪽을 진행합니다.
- 백엔드 배포 담당자는 CD 성공 직후 `nginx` 이미지가 배포 전과 동일하고 `fastapi`만
  새 주소인지 확인합니다. 이어 서비스 URL의 `/api/openapi.json`이 HTTP 200인지와
  `POST /v1/news/feed` 정의를 확인합니다. 비공개 서비스는 호출 권한이 있는 인증으로
  확인합니다. 프론트 배포 후에는 프론트 담당자와 화면·API·썸네일을 함께 확인합니다.
- 실제 배포·화면 통합 검증 결과는 실행 후 PR 또는 이슈에 기록합니다. FastAPI 단독
  스모크 테스트 통과를 이 통합 검증의 완료로 표시하지 않습니다.

백엔드 저장소의 **Settings → Secrets and variables → Actions**에서 워크플로가 참조하는 값을 설정합니다.

| GitHub 설정 | 이름 | 용도 |
| --- | --- | --- |
| Secrets | `GCP_SA_KEY` | GitHub Actions의 GCP 배포용 서비스 계정 JSON 키 |
| Variables | `GCP_PROJECT`, `RUN_REGION` | Cloud Run 배포 프로젝트와 리전 |
| Variables | `AR_REGION`, `AR_REPOSITORY` | 이미지 저장소의 리전과 이름 |

실행 계정, Cloud SQL 연결과 `PGHOST`·`PGPORT`·`PGDATABASE`·`PGUSER`·`PGPASSWORD`,
`DB_POOL_MAX_SIZE`, `READER_COOKIE_SECRET` 설정은 기존 Cloud Run 서비스에 유지합니다.
DB 비밀번호는 Secret Manager의 `news-db-password`, 독자 쿠키 서명 키는
`news-reader-cookie-secret` 버전 `1`을 참조하는 기존 설정을 사용합니다.
이번 CD는 이미지 갱신만 하므로 GitHub Variables의 DB·실행 계정·풀 크기를 바꾸는 것만으로
Cloud Run 설정이 갱신되지는 않습니다. 해당 설정 변경은 인프라 담당 절차로 적용합니다.

일반 환경변수와 Secret 참조 버전 변경은 새 리비전의 설정으로 적용합니다.
`DB_POOL_MAX_SIZE`는 새 인스턴스의 FastAPI 프로세스가 시작할 때 읽으며 기존 실행
프로세스의 값은 자동 변경되지 않습니다. Secret 환경변수도 인스턴스 시작 시
읽습니다. DB 비밀번호가 `latest`를 참조하면 새 인스턴스가 시작할 때 최신 값을
읽지만, 쿠키 서명 키의 고정 버전 `1`은 새 Secret 버전을 추가하는 것만으로 바뀌지
않습니다. 이미지 롤백도 `latest` Secret의 예전 값을 복원하지 않습니다.
자세한 반영 시점은 Google의 [환경변수](https://docs.cloud.google.com/run/docs/configuring/services/environment-variables)와
[Secret 안내](https://docs.cloud.google.com/run/docs/configuring/services/secrets)를 참고합니다.

Cloud Run의 DB 연결 수는 인스턴스 수와 프로세스당 풀 상한에 따라 늘어납니다.
기사 적재와 관리 접속도 포함해 Cloud SQL 연결 한도에 여유가 있도록 풀 상한을 정합니다.
Cloud Run 실행 계정에는 Cloud SQL 연결과 해당 Secret 읽기 권한이 필요합니다. GCP 리소스 정의는 [infra 저장소](https://github.com/asac-news-rec/infra)에서 관리합니다.

Nginx와 백엔드의 이미지 업로드·배포는 각 저장소에서 수행합니다. 신규 서비스·권한·리소스를
추가하지 않으며 백엔드의 Nginx 이미지 빌드·업로드 비용을 줄입니다.
문제 발생 시 이전에 검증한 FastAPI 이미지 주소로 `--container fastapi --image ...`만
갱신해 롤백합니다. 서비스 전체 리비전으로 되돌리면 프론트 버전도 함께 되돌아갈 수 있으므로,
전체 리비전 롤백이 필요한 경우 프론트 담당자와 함께 확인합니다.
배포 전후의 `nginx` 이미지가 같은지, `fastapi`만 새 주소로 바뀌었는지 확인합니다.

### 이전 이미지 확인과 롤백

1. GCP 콘솔 → Cloud Run → `news-feed` → 업데이트 기록(리비전 목록)에서 이전에
   정상 동작한 리비전의 `fastapi` 이미지 전체 주소를 확인합니다. Artifact Registry의
   `news-feed` 이미지 버전·커밋 SHA 태그 또는 이전 백엔드 CD의 빌드·업로드 로그에서도
   찾을 수 있습니다. 현재 `nginx` 이미지 주소도 기록합니다.
2. 백엔드만 되돌릴 때는 확인한 이전 주소로 아래 명령을 실행합니다. 프로젝트·리전은
   현재 운영 대상 값으로 지정합니다. 새 리비전의 준비 상태와 트래픽 대상도 확인합니다.

```bash
gcloud run services update news-feed \
  --project "$GCP_PROJECT" \
  --region "$RUN_REGION" \
  --container fastapi \
  --image "$PREVIOUS_FASTAPI_IMAGE"
```

3. 갱신 후 현재 Nginx 이미지 유지와 `/api/openapi.json` 응답을 확인합니다.
   이전 리비전으로 트래픽을 전환하는 방식은 당시 Nginx와 환경설정도 함께 사용하는
   것이므로, 위 FastAPI 이미지 갱신과 구분해 프론트 담당자와 협의합니다.

**[확인 필요]** `infra`가 이 Cloud Run 서비스를 Terraform state에서 관리하는지는
인프라 담당자가 확인합니다. Terraform 코드가 이미지 주소를 관리한다면 다음
`apply`에서 CD가 바꾼 이미지가 되돌아갈 수 있으므로 plan의 이미지 변경을 검토하고
소유권을 합의합니다. 관련 제외 설정이 이미 있다고 가정하지 않습니다.
이번 문서 수정에서는 실제 배포·롤백·Terraform 적용을 수행하지 않았습니다.

## 릴리스 초안

[Release Drafter](.github/workflows/release-drafter.yml)는 백엔드 `main`에 변경이 들어오면
[릴리스 형식](.github/release-drafter.yml)에 맞춰 머지된 PR 제목과 번호를 초안에 모읍니다.
GitHub의 **Releases**에서 배포할 `main` 커밋의 CI가 성공했는지 확인한 뒤
**Publish release**로 공개합니다. CD가 CI 성공 기록을 찾지 못해 실패하면,
해당 커밋의 CI 성공을 확인한 후 실패한 CD 실행을 다시 실행합니다.

## 협업 문서

이슈·브랜치·PR 절차는 [CONTRIBUTING.md](CONTRIBUTING.md), AI 코딩 도구의 작업 지침은 [AGENTS.md](AGENTS.md)를 참고합니다.

## API 버전 경로

업무 API는 URL 접두사 `/v1`로 버전을 구분합니다. FastAPI의 `api_v1` 라우터에
업무 경로를 등록하고 `app.include_router(api_v1, prefix="/v1")`로 연결합니다.
Nginx는 `/api/` 접두사만 제거하므로 프론트에서 사용하는 주소는 다음과 같습니다.

| 용도 | 메서드 | 외부 주소 | FastAPI 직접 호출 |
| --- | --- | --- | --- |
| 익명 독자 발급 | POST | `/api/v1/user/anonymous` | `/v1/user/anonymous` |
| 피드 | POST | `/api/v1/news/feed` | `/v1/news/feed` |
| 기사 상세 | GET | `/api/v1/news/{article_id}` | `/v1/news/{article_id}` |
| 좋아요 등록 | PUT | `/api/v1/news/{article_id}/like` | `/v1/news/{article_id}/like` |
| 좋아요 해제 | DELETE | `/api/v1/news/{article_id}/like` | `/v1/news/{article_id}/like` |
| 대분류 | POST | `/api/v1/category` | `/v1/category` |
| 중분류 | POST | `/api/v1/subcategory` | `/v1/subcategory` |

상태 확인 `/health`와 API 문서 `/docs`·`/openapi.json`은 버전 접두사를 붙이지 않습니다.
피드는 `POST /v1/news/feed`만 제공하며, 버전 없는 `POST /news/feed`는 제거했습니다.
프론트는 외부 경로 `/api/v1/news/feed`를 사용해야 합니다.
익명 독자·상세·좋아요·카테고리의 버전 없는 호환 경로는 현재 `app`에 직접 등록되어
있으며, `include_in_schema=False`로 OpenAPI에는 v1 업무 경로만 표시합니다.
쿠키 이름과 인증 방식은 유지합니다.
v2에서 호환되지 않는 변경을 도입할 때는 별도 라우터·모델을 정의해 `/v2`에 연결합니다.
이번 변경은 로컬 코드 변경이며 실제 서비스 배포는 수행하지 않았습니다.
롤백할 백엔드 이미지가 `/v1`·상세 경로를 제공하는지 확인하고 프론트 버전과 함께
복원 범위를 정합니다. 기존 백엔드 이미지를 보관하며 새 인프라와 추가 비용은 없습니다.

`POST /api/v1/news/feed`는 본문을 조회·전송하지 않습니다.
본문은 `GET /api/v1/news/{article_id}` 상세 조회의 `content.paragraphs`에서 제공합니다.
배포 전에 프론트가 `/api/v1/news/feed`와 상세 조회를 사용하도록 전환됐는지 확인합니다.
상세 SQL은 `tests/test_repository_postgres.py`에서 실제 PostgreSQL로 본문·독자별 좋아요·
좋아요 해제·미존재 기사를 검증합니다. 기존 CI의 임시 PostgreSQL 환경에서 자동 실행합니다.
