# 에이전트 프로젝트 참조

> Last Updated: 2026-11-12

백엔드 저장소의 구조, 파일별 책임과 팀 소유권을 설명합니다.
상태 표기(**[현재]** / **[계획]** / **[미정]**)는 [AGENTS.md](../../AGENTS.md)를 따릅니다.

## 프로젝트 구조 [현재]

| 경로 | 역할 |
| --- | --- |
| `app/main.py` | FastAPI 라우트와 요청·응답 처리 |
| `app/config.py`, `app/db.py` | DB 환경변수와 PostgreSQL 연결 |
| `app/repository.py` | 피드·카테고리 조회와 좋아요·변경 이력 처리 |
| `logging/` | 후속 배포를 위해 로컬에 보관한 반환 로그 코드와 테스트 |
| `compose.yaml`, `.env.example` | 로컬 PostgreSQL 18·FastAPI·Nginx 실행과 환경변수 예시 |
| `Dockerfile`, `pyproject.toml`, `uv.lock` | Python 3.14 기반 FastAPI 이미지와 잠금 의존성 |
| `nginx/default.conf` | 로컬 Compose의 Nginx 설정 |
| `nginx/Dockerfile`, `nginx/default.conf.template` | Cloud Run용 Nginx 이미지와 API 프록시 설정 |
| `tests/`, `pytest.ini` | 백엔드 API와 PostgreSQL 조회 검증 |
| `generate/`, `exports/` | 기사·썸네일 생성, 기사 적재, DB 백업·복원 |
| `.github/workflows/` | 브랜치 이름 검사, 백엔드 CI, Cloud Run CD |
| `.github/scripts/smoke-containers.sh` | Nginx·FastAPI 컨테이너 실행 및 응답 검사 |
| `.github/ISSUE_TEMPLATE/`, `.github/PULL_REQUEST_TEMPLATE.md` | 이슈와 PR 양식 |
| `AGENTS.md`, `.claude/docs/`, `CONTRIBUTING.md` | 에이전트 진입 문서, 상세 가이드, 협업 규칙 |

위 표는 백엔드 작업본의 파일을 기준으로 합니다. GitHub 반영과 실제 Cloud Run 배포 상태는
워크플로 실행 기록에서 확인합니다. 루트 `docs/`는 로컬 참고 문서 폴더입니다.

## 팀 소유권

| 도메인 | 팀원 | 책임 | 저장소 |
| --- | --- | --- | --- |
| 인프라 | 장주현 (`josiah113366-sketch`) | GCP 리소스, IAM, 공용 개발 인프라 | `infra` |
| 뉴스 서버·기사 | 태원 (`taewonkim2`) | 뉴스 API, 기사 생성·적재, 뉴스 DB, 백엔드 CI/CD | `backend` |
| 프론트·행동 수집 | 김세호 (`hosose`) | 화면과 사용자 행동 이벤트 수집 | `frontend` |
| 데이터 처리·모델 | 신윤모 (`yoonmo335`) | Airflow DAG, BigQuery, 피처·학습, 청사진 | `data-ml-pipeline`, `blueprint` |
| 추론 서버 | [미정] | 서버 배포와 점수 계산 역할 분담 | [미정] |

백엔드 변경이 API 계약, Cloud SQL 접속 또는 이벤트 수집에 영향을 주면 해당 담당자를
리뷰에 포함합니다. PR Assignee는 작성자 본인으로 두고, 팀의 승인 절차는
[워크플로 가이드](agent-workflow-reference.md)를 따릅니다.

## 실행과 배포 범위

- 로컬 실행은 루트 `compose.yaml`을 사용합니다. Nginx는 같은 상위 폴더에 있는
  프론트 저장소의 `dist/`를 읽고, API 요청을 Compose 서비스 `api:8000`으로 전달합니다.
- GitHub Actions는 프론트 `main`의 빌드 결과와 백엔드 코드로 두 Docker 이미지를 만듭니다.
  CD는 두 이미지를 Artifact Registry에 올려 Cloud Run 서비스 `news-feed`에 함께 적용합니다.
- Cloud SQL, IAM, 네트워크 등 GCP 리소스 정의는 `infra`에서 관리합니다.
  백엔드는 Cloud Run 실행 구성, DB 접속 변수, Secret Manager 참조를 워크플로에 정의합니다.
- 기사·이미지 생성과 기사 적재는 `generate/`에서 진행합니다. API는 PostgreSQL에 저장된
  기사와 `image_url`을 조회합니다.

실행 명령과 GitHub 설정 이름은 [백엔드 README](../../README.md), 클라우드 리소스와의
경계는 [Terraform 참조](agent-terraform-reference.md)를 참고합니다.

## 변경 검증

- [ ] API나 DB 접근 변경은 관련 `pytest` 테스트에서 확인했습니다.
- [ ] Compose 변경은 `docker compose config --quiet`로 확인했습니다.
- [ ] 이미지·프록시 변경은 PR의 Docker 스모크 테스트로 확인했습니다.
- [ ] 로컬 환경변수를 추가했다면 루트 `.env.example`에 이름을 기록했습니다.
- [ ] 배포용 변수나 Secret 참조가 바뀌면 README의 Actions 설정 안내를 갱신했습니다.
- [ ] 외부 저장소나 GCP 리소스에 영향이 있으면 PR에 범위와 검증 결과를 적었습니다.
