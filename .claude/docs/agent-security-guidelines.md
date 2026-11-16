# 에이전트 보안 가이드

> Last Updated: 2026-11-12

백엔드의 시크릿, 자격 증명, IAM, 워크플로 권한을 다룰 때 참고합니다.

## Secrets

- 로컬 접속값과 API 키는 루트 `.env`에 두고, 공유 예시는 `.env.example`에 둡니다.
- 서비스 계정 JSON 키, 개인 키, ADC 파일, Terraform state·plan 및 실값 `.tfvars`를
  커밋하지 않습니다.
- 시크릿 값은 코드, 로그, PR 본문, 커밋 메시지, 이슈, 채팅에 포함하지 않습니다.
- Cloud Run의 FastAPI에는 Secret Manager 참조를 통해 DB 비밀번호를
  `PGPASSWORD`로 주입합니다. 배포 설정에는 Secret 이름과 버전을 적습니다.
- GitHub Actions Variables에는 프로젝트·리전, 이미지 저장소, 실행 계정 이메일,
  DB 연결 이름과 같은 배포 설정을 둡니다. 자격 증명은 Actions Secrets에서 참조합니다.

## GitHub Actions 인증 [현재 코드]

| 설정 | 용도 |
| --- | --- |
| `GCP_SA_KEY` | CD에서 Google Cloud에 인증하는 배포 계정의 JSON 키. Artifact Registry 업로드와 Cloud Run 배포에 사용합니다. |
| `WAS_SERVICE_ACCOUNT` | Cloud Run에 배포된 서비스의 실행 계정 이메일. Cloud SQL 연결과 지정된 Secret 읽기 권한이 필요합니다. |

[CD 워크플로](../../.github/workflows/cd.yml)는 `GCP_SA_KEY`를
`credentials_json`에 전달합니다. 향후 인증 방식을 바꿀 때는 OIDC 기반 Workload
Identity Federation을 우선 검토하고, 변경 사항을 워크플로와 배포 안내에 함께 반영합니다.

## IAM과 네트워크

- 배포 계정과 실행 계정은 용도에 맞는 최소 권한을 사용합니다. DB 비밀번호 읽기 권한은
  해당 Secret 범위에 부여합니다.
- DB 접근 권한은 Cloud SQL에 연결할 수 있는 GCP IAM 권한과 PostgreSQL 사용자에게
  부여된 SQL 권한을 함께 확인합니다.
- Cloud SQL 접속 경로, 방화벽과 IAM 리소스 정의는 `infra`에서 관리합니다.
  백엔드 변경으로 공개 접근 범위나 권한이 달라지면 PR에 이유와 롤백 방법을 적습니다.

## 워크플로 검증

- 워크플로의 `permissions`는 필요한 최소 범위로 설정합니다.
- PR 제목이나 코멘트처럼 외부 입력을 셸 코드에 직접 보간하지 않습니다.
- 커밋 전 상태와 diff에서 자격 증명이나 데이터 파일이 섞였는지 확인합니다.
  `git diff --check`를 실행하고, 로컬에 `actionlint`가 있으면 함께 사용합니다.
