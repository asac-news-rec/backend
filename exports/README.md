# 기사 DB 백업 복원 안내

## reader_id 변경 후 최신 백업

`newsdb_2026-11-04_reader_id.dump`는 reader_id 컬럼으로 통일한 최신 전체 DB 백업입니다.
기사 250건, 좋아요 12건, 변경 이력 24건을 포함합니다. 테이블이 없는 빈 DB에는 아래 백업을 선택하세요.

```bash
docker compose exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges --exit-on-error --single-transaction' \
  < exports/newsdb_2026-11-04_reader_id.dump
```

기존 `newsdb_2026-11-04.dump`는 user_id 컬럼을 사용하는 변경 전 스냅샷으로 보존했습니다.
기존 백업을 이미 복원한 DB에서는 루트 README의 `migrations/20261104_reader_id.sql`을 적용하세요.
두 전체 백업을 같은 DB에 연달아 복원하지 마세요.


## 2026-11-04 전체 DB 백업

`newsdb_2026-11-04.dump`는 기사 250건과 현재 좋아요·변경 이력 테이블의 구조 및 데이터를 포함한 전체 프로젝트 DB 백업입니다. 기존 `news_articles.dump`는 이전 시점의 기사 전용 백업이므로 구분해서 사용합니다. 이미지 파일과 DB 접속 비밀번호는 이 백업에 포함하지 않습니다.

아래 명령은 `.env` 설정과 PostgreSQL 실행을 마친 **테이블이 없는 빈 대상 DB**에서 사용합니다. 기존 테이블이 있는 DB에 덮어쓰는 명령이 아닙니다. 아래의 기사 전용 복원과 둘 중 하나만 선택하세요.

```bash
docker compose exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges --exit-on-error --single-transaction' \
  < exports/newsdb_2026-11-04.dump
```

오늘 생성 원본과 이미지는 `generate/output_with_thumbnail/2026-11-04/`에 있습니다. 백업의 이미지 URL은 로컬 `http://localhost:8001` 기준이므로, 프로젝트 루트에서 다음 명령으로 이미지를 제공합니다.

```bash
python -m http.server 8001 --bind 127.0.0.1 --directory generate/output_with_thumbnail
```

전체 백업 생성 명령(프로젝트 루트에서 실행):

```bash
docker compose exec -T postgres sh -c \
  'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc --no-owner --no-privileges' \
  > exports/newsdb_2026-11-04.dump
```

---

`news_articles.dump`는 PostgreSQL의 `pg_dump`로 만든 백업 파일입니다.
`public.news_articles` 테이블 구조와 백업 시점의 기사 데이터가 포함되어 있습니다.
좋아요 테이블과 이미지 파일은 포함하지 않습니다. 이 파일을 읽을 때는 `psql`이 아니라 `pg_restore`를 사용합니다.

## 1. 파일 준비

이 저장소를 내려받고 백업 파일을 아래 위치에 넣습니다.
명령은 `compose.yaml`이 있는 프로젝트 루트에서 실행합니다.

```text
backend/
  compose.yaml
  .env.example
  exports/
    README.md
    news_articles.dump
```

Docker Desktop을 설치하고 실행해 두세요. 아래 방법은 프로젝트의 PostgreSQL 18 컨테이너를 사용하므로 PC에 PostgreSQL을 따로 설치할 필요가 없습니다.

## 2. DB 접속 설정

아직 `.env`가 없는 경우에만 프로젝트 루트에서 실행합니다.
이미 `.env`가 있다면 복사 명령은 생략하고 기존 설정을 사용합니다.

```bash
cp .env.example .env
```

`.env`를 편집해 본인이 사용할 비밀번호를 입력합니다.
백업을 만든 사람의 비밀번호와 같을 필요는 없습니다.

```dotenv
PGHOST=127.0.0.1
PGPORT=5433
PGDATABASE=newsdb
PGUSER=recommend
PGPASSWORD=본인이_정한_비밀번호
```

위 예시의 마지막 값은 실제 비밀번호로 변경합니다. `.env`는 공유하거나 Git에 올리지 않습니다.
기존 DB 볼륨이 있다면 기존 계정 정보를 사용하세요. `.env`를 수정하는 것만으로 기존 DB의 비밀번호가 바뀌지는 않습니다.

## 3. PostgreSQL 실행

```bash
docker compose up -d --wait
docker compose ps
```

최초 실행에서는 PostgreSQL 이미지를 다운로드하고, 빈 볼륨에 `.env`의 DB와 계정을 생성합니다.
`postgres`가 실행되고 상태가 `healthy`인지 확인합니다.
이 단계에서는 기사 테이블이 아직 만들어지지 않습니다.

## 4. 기사 테이블 복원

**`public.news_articles` 테이블이 없는 DB에 처음 복원하는 명령입니다.**
이미 기사를 적재했거나 한 번 복원했다면 같은 명령을 반복하지 마세요.

```bash
docker compose exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --no-owner --no-privileges --exit-on-error --single-transaction' \
  < exports/news_articles.dump
```

이 명령은 백업 파일에서 테이블을 생성하고 기사 데이터를 넣습니다.
다시 `load_postgres`를 실행할 필요는 없습니다.

| 부분 | 의미 |
| --- | --- |
| `docker compose exec -T postgres` | 실행 중인 PostgreSQL 컨테이너에서 명령 실행. 파일 입력을 위해 TTY 비활성화 |
| `pg_restore` | PostgreSQL 백업 파일 복원 |
| `-U`, `-d` | 컨테이너에 설정된 사용자와 대상 DB 사용 |
| `--no-owner --no-privileges` | 원본 DB의 소유자·권한 설정을 적용하지 않고 현재 계정으로 복원 |
| `--exit-on-error` | 오류가 발생하면 중단 |
| `--single-transaction` | 전체 복원을 한 트랜잭션으로 처리하여 실패 시 해당 복원 변경 취소 |
| `< exports/news_articles.dump` | 내 PC의 백업 파일을 복원 명령의 입력으로 전달 |

정상 완료되어도 별도 메시지 없이 터미널 프롬프트로 돌아올 수 있습니다. 다음 단계에서 데이터를 확인하세요.

## 5. 복원 결과 확인

```bash
docker compose exec -T postgres sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT COUNT(*) AS article_count FROM public.news_articles;"'
```

기사 건수가 표시되면 복원된 것입니다.
DBeaver에서도 다음 값으로 연결해 확인할 수 있습니다. `.env`에서 값을 변경했다면 변경한 값을 사용합니다.

| 항목 | 기본값 |
| --- | --- |
| Host | `127.0.0.1` |
| Port | `5433` |
| Database | `newsdb` |
| Username | `recommend` |
| Password | 본인 `.env`의 `PGPASSWORD` 값 |

SQL 편집기에서 실행합니다.

```sql
SELECT COUNT(*) FROM public.news_articles;

SELECT id, title, published_at, image_url
FROM public.news_articles
ORDER BY published_at DESC
LIMIT 10;
```

## 6. 이미지 확인

이미 공유받은 이미지 폴더를 사용합니다. 백업에는 이미지의 URL 문자열만 들어 있고 이미지 파일 자체는 들어 있지 않습니다.
이미지 URL이 `http://localhost:8001/...`인 경우, 프로젝트 루트에서 다음 명령을 실행합니다.

```bash
python -m http.server 8001 \
  --bind 127.0.0.1 \
  --directory generate/output_with_thumbnail
```

이 터미널은 이미지를 확인하는 동안 켜 둡니다.
공유받은 폴더의 날짜·파일명 구조가 원본과 같아야 DB의 이미지 URL로 접근할 수 있습니다.

## 자주 만나는 문제

| 증상 | 처리 |
| --- | --- |
| 백업 파일을 찾을 수 없음 | 프로젝트 루트에서 실행했는지, `exports/news_articles.dump` 파일이 있는지 확인 |
| `postgres` 서비스가 실행 중이 아님 | Docker Desktop 실행 후 `docker compose up -d --wait` |
| 호스트 포트가 이미 사용 중 | `.env`의 `PGPORT`를 사용하지 않는 포트로 변경하고 Compose 재실행. DBeaver 포트도 변경 |
| `relation ... already exists` | 대상 DB에 테이블이 이미 있음. 이 안내는 최초 복원 기준이므로 중단하고 기존 데이터 보존 여부에 따라 별도 이전 방법 결정 |
| 비밀번호 인증 실패 | 기존 DB 계정 정보와 `.env` 설정 확인. 기존 볼륨은 `.env` 수정만으로 계정이 바뀌지 않음 |

이 안내는 기사 테이블만 복원합니다. 좋아요 기능에 필요한 테이블은 백업에 포함되어 있지 않습니다.
