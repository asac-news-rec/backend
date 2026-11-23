# 에이전트 워크플로 참조

> Last Updated: 2026-11-23

백엔드의 이슈, 브랜치, 커밋, PR과 배포 흐름을 설명합니다.
협업 규칙은 [CONTRIBUTING.md](../../CONTRIBUTING.md), 실행·검증 명령은
[README.md](../../README.md)를 참고합니다.

## 워크플로 개요

```text
이슈 → 이슈에서 브랜치 생성 → 작업·로컬 검증 → Draft PR
→ 자동 검사와 셀프 리뷰 → Ready for review → 팀원 리뷰
→ 팀원 2명 승인과 대화 해결 → Squash merge
→ main 푸시 CI와 릴리스 초안 갱신 → Publish release → 태그 커밋의 CI 확인 → Cloud Run CD
```

## 에이전트 기본 규칙

- 이슈·PR 생성과 수정, 원격 브랜치 push·삭제, merge, label·Ruleset·Secret 변경 등
  GitHub 원격 작업은 사용자가 승인한 범위에서 진행합니다.
- 이슈와 PR의 Assignee는 생성자 본인으로 두고, 저장소에 등록된 label 중 변경 성격에
  맞는 항목을 사용합니다.

## 이슈 생성

API·DB 접근·기사 적재·로그·Compose·배포 워크플로를 변경할 때 이슈에 목적, 작업 범위,
완료 조건을 적습니다. 범위 밖 후속 작업은 별도 이슈로 남깁니다. 아주 작은 문서 오타는
팀 규칙에 따라 바로 PR로 처리할 수 있습니다.

| 양식 | 제목 prefix | label | 주요 항목 |
| --- | --- | --- | --- |
| `feature.yml` | `[FEAT]` | `feature` | 목적, 작업 범위, 영향 영역, 완료 조건 |
| `bug.yml` | `[BUG]` | `bug` | 현상, 재현 방법, 기대·실제 동작, 환경 |
| `experiment.yml` | `[EXP]` | `experiment` | 가설, 실험 대상, 판정 기준과 결과 |
| `infra-request.yml` | `[인프라 요청]` | `infra-request` | 요청 유형, 환경, 변경 내용과 이유 |

Issue Form은 [이슈 양식 폴더](../../.github/ISSUE_TEMPLATE/)에 있습니다. 양식의
label이 자동 적용되려면 저장소에 같은 이름의 label이 있어야 합니다.

## 브랜치 이름

코드 변경 작업은 해당 이슈에서 `Development → Create a branch`를 선택해
`main` 기준으로 분기합니다. 이슈에 연결한 뒤
`<type>/<이슈번호>-<영어-소문자-슬러그>` 형식의 이름을 입력합니다.
슬러그에는 영어 소문자, 숫자, 하이픈을 씁니다.

브랜치를 만든 후 로컬 백엔드 저장소에서 가져옵니다. 아래의 이슈 번호와 이름은 예시입니다.

```bash
git fetch origin
git switch feat/42-add-backend-ci-cd
```

[브랜치 이름 검사](../../.github/workflows/branch-name-policy.yml)는 PR의 작업 브랜치명을
검사합니다. GitHub Revert가 만드는 `revert-<PR번호>-...` 브랜치도 허용합니다.

## 커밋 메시지

형식은 `<type>: <한국어 설명>`이며 제목은 50자 이내로 작성합니다. 한 커밋에는
하나의 논리적 변경을 담습니다.

| type | 사용 상황 |
| --- | --- |
| `feat` | API·기사 적재 기능 또는 CI/CD 추가 |
| `fix` | API, DB 쿼리, 프록시나 배포 오류 수정 |
| `exp` | 조회 방식, 로깅, 실행 방식 비교 실험 |
| `docs` | 문서 추가 또는 수정 |
| `refactor` | 동작 변화 없는 구조 정리 |
| `chore` | 저장소 기본 설정과 관리 작업 |

```text
feat: 백엔드 CI/CD 워크플로 추가
fix: 뉴스 피드 필터 처리 수정
docs: 백엔드 실행 가이드 갱신
```

## PR 생성과 검증

- [ ] `git diff --check`를 실행했습니다.
- [ ] Python 변경은 Python 3.14와 `uv`로 관련 `pytest`를 실행했습니다.
- [ ] Compose 변경은 `docker compose config --quiet`로 확인했습니다.
- [ ] Docker 이미지나 Nginx 설정이 바뀌면 PR의 스모크 테스트 결과를 확인했습니다.
- [ ] 시크릿, 서비스 계정 키, Terraform state·실값 `.tfvars`가 포함되지 않았습니다.

[PR 양식](../../.github/PULL_REQUEST_TEMPLATE.md)에 작업 내용, 변경 사항, 관련 이슈,
검증 결과와 리뷰어 참고사항을 적습니다. 본문에 `Closes #이슈번호`를 넣어 이슈와
연결합니다. Cloud Run, IAM, 비용 또는 롤백에 영향이 있으면 해당 내용을 PR에 적습니다.

Draft PR에서 diff와 검사 결과를 먼저 읽고 설명을 보강한 뒤 Ready for review로 전환합니다.
팀 리뷰에서 받은 질문에 답하고 필요한 부분을 검증한 뒤 해결된 대화를 resolve합니다.

## 리뷰와 머지

팀 절차는 **Ready 상태, 팀원 2명 승인, 대화 해결, 필요한 체크 통과**입니다.
GitHub의 `main` 보호 규칙과 필수 체크가 실제로 켜져 있는지는 **[확인 필요]**입니다.
리뷰어는 API·DB·프론트 계약, 자격 증명 처리, 배포 권한과 검증 결과를 확인합니다.

팀 머지 방식은 **Squash and merge**입니다. 제목은 `<type>: <설명> (#PR번호)` 형식을
사용합니다. `Closes #이슈번호`로 연결된 이슈는 기본 브랜치에 머지될 때 닫힙니다.
머지 후 브랜치 자동 삭제는 저장소 설정을 따릅니다.

## CI와 CD [현재 코드]

| 워크플로 | 실행 조건과 검사 범위 |
| --- | --- |
| [branch-name-policy.yml](../../.github/workflows/branch-name-policy.yml) | PR 브랜치 이름 형식 검사 |
| [ci.yml](../../.github/workflows/ci.yml) | PR 및 `main` 푸시에서 `pytest` 실행. PR에서는 FastAPI 이미지 단독 스모크 테스트도 실행 |
| [release-drafter.yml](../../.github/workflows/release-drafter.yml) | `main` 푸시에서 릴리스 초안 갱신 |
| [cd.yml](../../.github/workflows/cd.yml) | 릴리스 공개 후 태그 커밋의 `main` 푸시 CI 성공을 확인하고 FastAPI 이미지만 업로드·갱신 |

스모크 테스트는 FastAPI의 8000번 포트에서 `/openapi.json`의 HTTP 200과
`POST /v1/news/feed` 정의를 직접 확인합니다. 검사 통과 후 FastAPI 이미지 하나만
업로드하고, 기존 `news-feed`의 `fastapi` 컨테이너 이미지만 갱신합니다.
Nginx와 서비스 설정은 유지하며, 프록시·화면 연동은 별도 확인합니다.
백엔드 이미지는 공개한 릴리스 태그의 커밋으로 빌드합니다.
최초 구성·동시 배포 주의사항·롤백은 [배포 안내](../../README.md#cloud-run-배포)를 따릅니다.

## 충돌과 후속 수정

- `main`과 충돌하면 변경을 가져와 팀 워크플로에 따라 rebase합니다.
  이미 푸시한 브랜치의 이력을 바꿀 때는 변경 내용을 확인하고 `--force-with-lease`를 사용합니다.
- 리뷰 요청을 반영한 뒤 새 커밋을 푸시하고 재리뷰를 요청합니다.
- 별도 이슈로 분리한 변경은 새 브랜치와 PR을 만들고 양쪽 PR에 서로의 링크를 남깁니다.

## 문제 해결

- **CD 실행 확인** — GitHub에서 릴리스를 공개했는지 확인합니다. CD의 CI 확인 단계가
  실패했다면 태그 커밋의 `main` 푸시 CI 성공을 확인하고 해당 CD 실행을 다시 실행합니다.
- **GCP 인증이나 업로드 실패** — `GCP_SA_KEY`, 대상 프로젝트·리전, Artifact Registry
  저장소, 배포 계정의 권한을 확인합니다.
- **Cloud SQL 접속 실패** — 기존 Cloud Run 서비스의 Cloud SQL 연결, 실행 계정 권한,
  Secret 참조와 DB 사용자 설정을 확인합니다. 현재 CD는 이 설정들을 변경하지 않습니다.
- **PR 머지 또는 이슈 닫힘 실패** — Draft 상태, 승인, 대화 해결, 필수 체크와
  `Closes #이슈번호`를 확인합니다.
