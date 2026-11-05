# 로컬 PostgreSQL

`compose.yaml`로 PostgreSQL 18을 실행합니다. 기사·이미지 생성 및 적재 코드는 `generate/`에 있습니다.

## Python 3.14 실행 환경

WAS는 표준 라이브러리의 `uuid7()`을 사용하므로 Python 3.14를 기준으로 합니다.
현재 확인한 환경은 `recommand314` / Python 3.14.10 / macOS arm64입니다.

```bash
cd /Users/taewonkim/Documents/final_project/backend

# recommand314 환경이 없는 경우에만 생성
conda create -n recommand314 python=3.14 pip
conda activate recommand314
python --version

# WAS + 기사·이미지 생성·DB 적재 의존성 설치
python -m pip install -r requirements.txt
python -m pip check

# WAS 실행 — backend 위치에서 실행
python -m uvicorn app.main:app --reload
```

`python --version`은 `Python 3.14.x`여야 합니다. 기존 환경은 생성 단계를 생략하고 활성화합니다.
API 문서: http://127.0.0.1:8000/docs

| 파일 | 역할 |
|---|---|
| `requirements.txt` | WAS·기사·이미지 생성·DB 적재의 통합 직접 의존성 |
| `generate/recommand_env.yml` | 로컬 참고용 Conda 설정 (Git 제외) |
| `generate/recommand_pip.txt` | 로컬 전체 설치 버전 스냅샷 (Git 제외) |

로컬에 `generate/recommand_pip.txt`를 보관한 경우에만, 환경 생성·활성화 후 전체 스냅샷을 복원할 수 있습니다. 이 파일은 Git에 포함되지 않습니다.
일반 프로젝트 실행에는 위의 `requirements.txt` 설치를 사용합니다.

```bash
python -m pip install -r generate/recommand_pip.txt
```

requirements는 Python 자체를 설치하지 않습니다. Conda 환경으로 Python을 먼저 선택합니다.
고정 버전은 현재 로컬 설치 상태를 기록한 것입니다. 다른 OS에서의 설치, 새 환경 재설치,
모델 다운로드와 기사·이미지 생성의 전체 실행 성공까지 보장하는 검증 결과는 아닙니다.

## 기사·이미지 생성 준비

Ollama·Gemma·SDXL의 역할, 최초 설치, 모델 다운로드와 실행 방법은 [생성 프로그램 README](generate/README.md)를 참고하세요.

## 최초 설정

`.env`에 접속값을 보관합니다. 이번 구성에서는 비밀번호를 임의 생성했습니다. Git에서 제외하고 화면·로그에 공유하지 않습니다.
다른 환경에서는 `.env.example`을 `.env`로 복사한 뒤 PGPASSWORD를 변경합니다.

```bash
cd /Users/taewonkim/Documents/final_project/backend
docker compose config --quiet
docker compose up -d --wait --wait-timeout 90
docker compose ps
```

호스트 `127.0.0.1:5433`을 컨테이너 `5432`에 연결합니다. 기본 DB는 newsdb, 사용자는 recommend입니다.
영속 볼륨 `asac-news-backend-postgres-data`를 사용하며, 기존 `recommend_pgdata`는 연결·변경하지 않습니다.
PostgreSQL 18 공식 이미지에 맞춰 볼륨은 `/var/lib/postgresql`에 연결합니다.

## 기사 적재

load_postgres는 실행 위치와 무관하게 backend/.env를 자동으로 읽습니다. 별도로 source 명령을 실행할 필요가 없습니다. CLI 옵션 > 기존 환경변수 > .env > 기본값 순으로 적용합니다.

```bash
cd /Users/taewonkim/Documents/final_project/backend
cd generate
python -m load_postgres --date 2026-11-02 --validate-only
python -m load_postgres --date 2026-11-02
```

load_postgres 실행 시 news_articles, article_likes, article_like_history 테이블을 준비하고 기사만 적재합니다.
Compose 실행만으로 테이블·기사를 생성하지 않으며 init.sql은 중복 추가하지 않았습니다.
좋아요 상태 변경·이력 기록은 현재 FastAPI와 `app/repository.py`에서 같은 트랜잭션으로 처리합니다.

## 상태 확인·중지·다시 실행

```bash
docker compose ps
docker compose logs --tail 50 postgres
docker compose stop
docker compose start
```

위 명령들은 저장 데이터를 유지합니다. `docker compose down`도 별도 `-v` 옵션 없이 실행하면 명명 볼륨을 보존합니다.
`docker compose down -v`는 프로젝트 DB 볼륨을 삭제하므로 데이터 보존이 필요하면 사용하지 않습니다.

`.env`의 초기 계정·비밀번호는 빈 볼륨 최초 초기화 때 적용됩니다. 기존 DB의 비밀번호를 바꾸려면 DB에서 변경해야 하며,
.env 값만 바꾼다고 DB 비밀번호가 자동 변경되지는 않습니다. 기존 recommend_pgdata 복구는 별도 작업입니다.

## reader_id 인터페이스

사용자 식별 필드는 요청·응답·좋아요 DB에서 `reader_id`로 통일합니다.
발급 경로는 기존 `POST /user/anonymous`를 유지하며 `{"reader_id": "UUID7"}`을 반환합니다.
뉴스 조회와 좋아요 요청은 `reader_id`를 보내야 하며, 이전 `user_id`만 보내면 422입니다.
뉴스 조회 응답의 최상위에도 `reader_id`를 포함합니다. 프론트 저장 키와 JSON 필드를 함께 갱신하세요.

신규 DB는 기사 적재기가 `reader_id` 컬럼으로 테이블을 생성합니다.
빈 DB에 백업을 복원할 때는 [백업 복원 안내](exports/README.md)의 `reader_id` 버전을 사용하세요.

Dockerfile도 루트 `requirements.txt`를 설치합니다. 통합 구성에 따라 WAS 이미지에도 Torch·Diffusers 등 생성용 패키지가 함께 설치됩니다.
