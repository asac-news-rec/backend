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

로컬에서는 FastAPI의 8000번 포트에 직접 요청합니다(`POST /v1/news/feed`). Cloud Run의 기존 Nginx를 거치는 외부 경로는 `POST /api/v1/news/feed`입니다. 기존 백엔드 Nginx 파일은 Git에서 제외한 `exports/nginx/`에 로컬 참고용으로 보관합니다.

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

날짜는 적재할 데이터 폴더에 맞게 바꿉니다. 먼저 `--validate-only`로 JSONL을 검증하고 통과한 뒤 실제 적재 명령을 실행합니다. 생성 모델 설정과 썸네일 URL 지정은 [기사·이미지 생성 및 적재 안내](generate/local_generate/README.md), 기존 DB 백업을 사용할 때는 [백업 복원 안내](exports/README.md)를 참고하세요.

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
`127.0.0.1:8000`으로 전달합니다. 실제 화면·API 통합 확인은 프론트 배포와 함께 수행합니다.

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

Cloud Run의 DB 연결 수는 인스턴스 수와 프로세스당 풀 상한에 따라 늘어납니다.
기사 적재와 관리 접속도 포함해 Cloud SQL 연결 한도에 여유가 있도록 풀 상한을 정합니다.
Cloud Run 실행 계정에는 Cloud SQL 연결과 해당 Secret 읽기 권한이 필요합니다. GCP 리소스 정의는 [infra 저장소](https://github.com/asac-news-rec/infra)에서 관리합니다.

Nginx와 백엔드의 이미지 업로드·배포는 각 저장소에서 수행합니다. 신규 서비스·권한·리소스를
추가하지 않으며 백엔드의 Nginx 이미지 빌드·업로드 비용을 줄입니다.
문제 발생 시 이전에 검증한 FastAPI 이미지 주소로 `--container fastapi --image ...`만
갱신해 롤백합니다. 서비스 전체 리비전으로 되돌리면 프론트 버전도 함께 되돌아갈 수 있으므로,
전체 리비전 롤백이 필요한 경우 프론트 담당자와 함께 확인합니다.
배포 전후의 `nginx` 이미지가 같은지, `fastapi`만 새 주소로 바뀌었는지 확인합니다.

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
기존 경로는 `app`에 직접 등록해 유지하며, `include_in_schema=False`로 OpenAPI에는
v1 업무 경로만 표시합니다. 별도 legacy 라우터는 사용하지 않습니다.
기존 피드는 본문을 포함하는 별도 응답 모델을 사용합니다. 쿠키 이름과 인증 방식은 동일합니다.
프론트는 별도 변경에서 새 주소로 전환할 수 있으며, 기존 경로 제거는 전환 완료 후 협의합니다.
v2에서 호환되지 않는 변경을 도입할 때는 별도 라우터·모델을 정의해 `/v2`에 연결합니다.
이번 변경은 로컬 코드 변경이며 실제 서비스 배포는 수행하지 않았습니다.
백엔드만 이전 이미지로 되돌리면 새 v1·상세 경로가 없어집니다. 이미 프론트가 새 주소로
전환했다면 기존 주소·본문 포함 피드를 사용하는 프론트 버전을 먼저 복원하고 백엔드를
복원합니다. 기존 백엔드 이미지를 보관하며, 새 인프라와 추가 비용은 없습니다.

`POST /api/news/feed`는 기존과 같이 `paragraphs`를 반환합니다.
`POST /api/v1/news/feed`는 본문을 조회·전송하지 않습니다.
본문은 `GET /api/v1/news/{article_id}` 상세 조회의 `content.paragraphs`에서 제공합니다.
배포는 기존 경로를 보존하는 백엔드를 먼저 적용하고, 프론트를 v1·상세 조회로 전환하는 순서입니다.
상세 SQL은 `tests/test_repository_postgres.py`에서 실제 PostgreSQL로 본문·독자별 좋아요·
좋아요 해제·미존재 기사를 검증합니다. 기존 CI의 임시 PostgreSQL 환경에서 자동 실행합니다.
