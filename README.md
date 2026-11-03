# 로컬 PostgreSQL

`compose.yaml`로 PostgreSQL 18을 실행합니다. 기사·이미지 생성 및 적재 코드는 `generate/`에 있습니다.

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
좋아요 상태 변경·이력 기록은 향후 뉴스 API에서 같은 트랜잭션으로 처리해야 합니다.

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
