# 에이전트 Terraform 참조

> Last Updated: 2026-11-12

백엔드 배포와 [infra 저장소](https://github.com/asac-news-rec/infra)의 Terraform 작업 경계를
설명합니다. Terraform의 리소스 정의와 적용 절차는 `infra`의 문서를 기준으로 합니다.

## 소유권 [현재 코드]

| 위치 | 책임 |
| --- | --- |
| `infra`의 `terraform/bootstrap/` | Terraform 상태 저장소와 초기 설정 |
| `infra`의 `terraform/envs/dev/` | Cloud SQL, 네트워크, IAM, GCP API 등 개발 환경 리소스 |
| `backend`의 `.github/workflows/cd.yml` | FastAPI·Nginx 이미지 업로드와 Cloud Run 서비스 `news-feed` 배포 |
| `backend`의 `README.md` | 배포 설정에 필요한 GitHub Actions Variables와 Secrets 안내 |

`infra`의 `apis.tf`와 `apis-platform.tf`에는 GCP API 활성화가
`google_project_service` 리소스로 정의되어 있습니다. 백엔드 CD는
`CLOUD_SQL_INSTANCE`로 연결 대상을 지정하고, `WAS_SERVICE_ACCOUNT`로 Cloud Run
실행 계정을 지정합니다.

## 리소스 변경이 필요한 경우

- 변경할 프로젝트·리전, 서비스 또는 리소스 이름, 필요한 권한을 적어 `infra` 담당과
  범위를 확인합니다. Secret 값은 요청 본문에 포함하지 않습니다.
- Terraform 검증과 plan은 변경을 담는 `infra` 저장소의 README 절차를 따릅니다.
  계획에서 리소스 삭제·교체가 보이면 영향과 롤백 방법을 확인합니다.
- 실제 `apply`·`destroy`는 사용자가 명확히 요청했을 때 진행합니다.
  state, plan, 실제 `.tfvars`와 서비스 계정 키는 커밋하지 않습니다.
- 백엔드 연결 정보나 실행 계정이 바뀌면 [README의 배포 설정](../../README.md#cloud-run-배포)과
  [보안 가이드](agent-security-guidelines.md)의 해당 항목을 확인합니다.
