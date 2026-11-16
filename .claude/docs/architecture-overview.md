# 아키텍처 개요

> Last Updated: 2026-11-12

뉴스 추천 프로젝트 전체에서 백엔드가 맡는 부분과 요청·배포 흐름을 설명합니다.
파일별 책임은 [에이전트 프로젝트 참조](agent-project-reference.md)를 참고합니다.

## 시스템 맥락

ASAC 뉴스 추천 프로젝트는 뉴스 서비스의 행동 로그를 모아 클릭 확률 예측 모델을
학습하고 그 결과를 서비스에 연결하는 것이 목표입니다. 이 저장소는 뉴스 API, 기사
생성·적재, 뉴스 DB 접근, 백엔드 CI/CD를 담당합니다. 전체 파이프라인 설계는
`blueprint` 저장소에서 관리합니다.

## 로컬 요청과 데이터 흐름 [현재]

```text
브라우저 → Nginx → HTML·CSS·JS 제공
                 └─ /api/ 요청 → FastAPI → PostgreSQL
기사·썸네일 생성 → JSONL·이미지 → 기사 적재기 → PostgreSQL
```

- FastAPI는 뉴스 피드와 카테고리를 조회하고, 익명 `reader_id`를 발급합니다.
  피드 조회는 PostgreSQL에서 조건에 맞는 기사를 발행 시각과 기사 ID 역순으로 읽습니다.
- 좋아요 상태와 변경 이력은 PostgreSQL에 기록합니다. 기사 응답의 `image_url`은
  기사 적재 시 저장한 값을 사용합니다.
- 반환 로그 기록과 전송은 후속 배포 범위입니다. 관련 코드와 테스트는 로컬
  `logging/`에 보관합니다.

## 로컬 실행 [현재]

`compose.yaml`이 PostgreSQL 18, FastAPI, Nginx를 실행합니다. Nginx는
`../frontend/dist/`를 제공하고 `/api/`를 `api:8000`으로 전달합니다. FastAPI는
Compose 내부의 `postgres:5432`에 연결합니다. 호스트에서 로컬 DB에 접속하는 기본
포트는 5433입니다. 실제 실행 명령은 [백엔드 README](../../README.md)를 참고합니다.

## Cloud Run 배포 [현재 코드]

1. 백엔드 릴리스를 공개하면 CD가 시작됩니다. 릴리스 태그의 커밋이
   `main` 푸시에서 CI를 통과했는지 확인합니다.
2. 릴리스 태그의 백엔드 커밋을 가져와 FastAPI와 Nginx API 프록시 이미지를 빌드합니다.
3. Nginx를 경유한 OpenAPI 응답과 뉴스 피드 경로 정의를 검사하고, 두 이미지를 Artifact Registry에
   업로드합니다.
4. Cloud Run 서비스 `news-feed`에 두 컨테이너를 적용합니다. 한 인스턴스에서
   Nginx는 80번으로 요청을 받고, `/api/`를 FastAPI의 `127.0.0.1:8000`으로 전달합니다.
5. FastAPI는 Cloud SQL PostgreSQL 접속 설정을 환경변수로 받습니다.
   `PGPASSWORD`는 Cloud Run이 Secret Manager에서 읽어 주입합니다.

이 순서는 [CD 워크플로](../../.github/workflows/cd.yml)에 정의되어 있습니다.
배포 결과와 Cloud SQL 접속 상태는 실제 실행 후 확인합니다. 스모크 테스트가 확인하는
범위는 Nginx를 경유한 FastAPI의 OpenAPI 응답과 뉴스 피드 경로 정의입니다.

## 프로젝트 전체 흐름 [계획]

| 단계 | 설계상 역할 |
| --- | --- |
| 수집 | 프론트 행동 이벤트와 백엔드 응답 기록을 모아 GCS에 저장 |
| 가공 | Airflow로 로그를 읽고 BigQuery에서 정제·집계 |
| 피처·학습 | 학습용 이력을 보관하고 모델을 학습해 MLflow에 기록 |
| 추천 서빙 | 온라인 피처와 예측 점수를 뉴스 피드에 연결 |

외부 로그 수신 서비스의 배포·연동 상태와 추론 서비스 운영 방식은 관련 담당자와 확인합니다.

## 변경 영향 체크리스트

- [ ] 프론트와 FastAPI 사이의 경로, 요청·응답 또는 `reader_id` 계약이 바뀌는가?
- [ ] DB 테이블, 기사 적재, 이미지 URL 또는 이벤트 로그에 영향이 있는가?
- [ ] 로컬 Nginx와 Cloud Run용 Nginx 양쪽 설정을 확인했는가?
- [ ] GCP 실행 계정, Secret, 리전 또는 비용에 영향이 있는가?
