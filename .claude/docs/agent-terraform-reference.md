# 에이전트 Terraform 참조

> Last Updated: 2026-11-23

백엔드 배포와 [infra 저장소](https://github.com/asac-news-rec/infra)의 Terraform 작업 경계를
설명합니다. Terraform의 리소스 정의와 적용 절차는 `infra`의 문서를 기준으로 합니다.

## 소유권 [현재 코드]

| 위치 | 책임 |
| --- | --- |
| `infra`의 `terraform/bootstrap/` | Terraform 상태 저장소와 초기 설정 |
| `infra`의 `terraform/envs/dev/` | Cloud SQL, 네트워크, IAM, GCP API 등 개발 환경 리소스 |
| `backend`의 `.github/workflows/cd.yml` | FastAPI 이미지 업로드와 기존 `news-feed`의 `fastapi` 이미지 갱신 |
| `backend`의 `README.md` | 배포 설정에 필요한 GitHub Actions Variables와 Secrets 안내 |

`infra`의 `apis.tf`와 `apis-platform.tf`에는 GCP API 활성화가
`google_project_service` 리소스로 정의되어 있습니다. 백엔드 CD는 기존 서비스의
Cloud SQL 연결·실행 계정·환경변수·Secret 참조를 유지하며 이미지 주소만 바꿉니다.
이 설정을 변경하거나 서비스를 처음 만들 때는 인프라 담당자와 구성을 확인합니다.

## Cloud Run 이미지와 Terraform의 경계

Cloud Run 서비스가 현재 Terraform state에서 관리되는지는 이 백엔드 변경만으로
확정할 수 없습니다. 인프라 담당자가 해당 리소스의 코드와 state를 확인해야 합니다.
Terraform이 이미지까지 관리한다면 다음 plan에 CD가 바꾼 이미지의 되돌림이
포함될 수 있습니다. `apply` 전에 plan을 확인하고, 이미지 갱신의 소유권과
필요한 제외 설정을 담당자와 합의합니다. `ignore_changes`가 이미 적용되어 있다고
가정하지 않으며, 이번 문서 수정에서 Terraform이나 실제 리소스는 변경하지 않습니다.

## 리소스 변경이 필요한 경우

- 변경할 프로젝트·리전, 서비스 또는 리소스 이름, 필요한 권한을 적어 `infra` 담당과
  범위를 확인합니다. Secret 값은 요청 본문에 포함하지 않습니다.
- Terraform 검증과 plan은 변경을 담는 `infra` 저장소의 README 절차를 따릅니다.
  계획에서 리소스 삭제·교체가 보이면 영향과 롤백 방법을 확인합니다.
- 실제 `apply`·`destroy`는 사용자가 명확히 요청했을 때 진행합니다.
  state, plan, 실제 `.tfvars`와 서비스 계정 키는 커밋하지 않습니다.
- 백엔드 연결 정보나 실행 계정이 바뀌면 [README의 배포 설정](../../README.md#cloud-run-배포)과
  [보안 가이드](agent-security-guidelines.md)의 해당 항목을 확인합니다.
