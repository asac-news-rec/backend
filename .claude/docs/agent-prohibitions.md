# 에이전트 금지 사항

> Last Updated: 2026-11-12

백엔드 저장소의 Git 작업, 로컬 데이터 관리, 배포 작업에서 지키는 기준입니다.

## Git / GitHub

- `main`에 직접 push하지 않습니다. 모든 변경은 PR을 거칩니다.
- GitHub 원격 변경은 사용자가 승인한 범위에서 수행합니다. 이슈·PR 생성과 수정,
  push·merge, 원격 브랜치·label·Ruleset·Secret 변경 등이 포함됩니다.
- 커밋 유형은 `feat`, `fix`, `exp`, `docs`, `refactor`, `chore`를 사용합니다.
- 이미 push된 브랜치를 사용자 동의 없이 force push하지 않습니다.
  rebase 후의 `--force-with-lease`는 팀 워크플로 가이드를 따릅니다.

## 로컬 데이터와 자격 증명

- `.env`, 서비스 계정 키, API 키, Terraform state·plan, 실값 `.tfvars`를
  커밋하거나 코드·로그에 기록하지 않습니다.
- `docker compose down -v`, `docker volume rm`처럼 로컬 DB 볼륨을 지우는 명령은
  사용자가 명확히 요청했을 때만 실행합니다.
- 프로젝트 ID, 버킷 이름, 실행 계정처럼 환경마다 달라지는 값은 환경변수나
  GitHub Actions Variables로 관리합니다.

## 클라우드와 배포

- Cloud SQL, IAM, 네트워크, GCP API 활성화 같은 리소스 변경은 `infra`의 소유 범위를
  확인하고 담당 저장소의 절차를 따릅니다.
- 실제 리소스 생성·삭제를 수반하는 `terraform apply`와 `destroy`는 사용자가
  명확히 요청했을 때만 실행합니다. state 조작과 리소스 교체는 계획과 영향을 먼저
  확인합니다.
- IAM 권한 확대, 외부 노출 변경, 서비스나 데이터의 삭제·교체는 영향과 롤백 방법을
  PR에 기록합니다. 광범위한 `roles/owner`, `roles/editor`를 편의상 부여하지 않습니다.
- 파일 이동·이름 변경과 서비스 동작 변경은 구분하고, 요청 범위를 벗어난 리팩터링은
  진행하지 않습니다.

## 문서

- 동작, 실행 명령, 설정이 바뀌면 관련 문서를 갱신합니다.
- `AGENTS.md`, `CONTRIBUTING.md`, `.claude/docs/` 사이에 충돌이 있으면 해당 내용을
  확인해 사용자에게 알립니다.
- 로컬 전용 문서와 설정은 저장소의 `.gitignore` 기준을 따릅니다.
