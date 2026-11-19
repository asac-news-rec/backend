#!/usr/bin/env bash
# pipeline 저장소 체크아웃 경로에서 실행합니다.
set -euo pipefail
: "${GENERATOR_IMAGE:?}" "${GH_TOKEN:?}" "${GITHUB_WORKSPACE:?}"
repo="asac-news-rec/data-ml-pipeline"
sha="${GENERATOR_IMAGE##*:}"
python3 "$GITHUB_WORKSPACE/.github/scripts/update-generator-image.py"
if git diff --quiet; then
  echo "main에 같은 이미지 주소가 이미 반영돼 있습니다."
  exit 0
fi

issue_title="[FEAT] 뉴스 생성기 이미지 갱신 ${sha}"
issue="$(gh issue list --repo "$repo" --state all --search "$sha in:title" --json number,title --jq ".[] | select(.title == \"$issue_title\") | .number" | head -1)"
if [[ -z "$issue" ]]; then
  issue_body="$(mktemp)"
  cat > "$issue_body" <<BODY
## 목적

업로드가 완료된 생성기 이미지로 Airflow의 다음 뉴스 생성 작업을 실행합니다.

## 작업 범위

- [ ] DAG와 Pod 템플릿의 이미지 주소를 갱신합니다.
- [ ] PR 검토 후 main에 반영하고 Airflow 동기화를 확인합니다.

## 영향받는 컴포넌트

Airflow DAG, 문서

## 완료 조건

- [ ] 아래 이미지 주소가 DAG와 Pod 템플릿에 동일하게 반영됩니다.
- [ ] Airflow에서 변경된 이미지로 실행되는지 확인합니다.

## 참고 사항

이미지 주소
${GENERATOR_IMAGE}

롤백은 이전 이미지 주소로 되돌립니다. 생성 주기와 건수는 이 변경의 대상에 포함되지 않습니다.
BODY
  issue_url="$(gh issue create --repo "$repo" --title "$issue_title" --body-file "$issue_body" --assignee @me --label feature)"
  issue="${issue_url##*/}"
fi

branch="chore/${issue}-update-generator-image-${sha:0:12}"
# 커밋된 이미지 변경만 별도 브랜치로 옮깁니다.
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
git switch -c "$branch"
git add dags/generate_news.py dags/pod_templates/news-generator.yaml
git diff --cached --check
git commit -m "chore: 생성기 이미지 버전 갱신"

# 같은 SHA를 재실행하면 먼저 생성한 PR을 그대로 사용합니다.
existing="$(gh pr list --repo "$repo" --state all --head "$branch" --json url --jq '.[0].url // empty')"
if [[ -n "$existing" ]]; then
  printf '이미 생성된 이미지 갱신 PR: %s\n' "$existing" >> "$GITHUB_STEP_SUMMARY"
  exit 0
fi

gh auth setup-git
git push origin "$branch"

body="$(mktemp)"
cp .github/PULL_REQUEST_TEMPLATE.md "$body"
export PR_BODY_FILE="$body" DEPLOY_ISSUE="$issue"
python3 - <<'PY'
import os
from pathlib import Path
path = Path(os.environ["PR_BODY_FILE"])
body = path.read_text()
body = body.replace("> 이 PR에서 무엇을 구현/수정했는지 간략하게 설명해 주세요.", "생성기 CD가 빌드·검사를 통과하고 Artifact Registry에 업로드한 이미지를 Airflow 실행 설정에 반영합니다.")
body = body.replace("-\n-\n", "- DAG와 Pod 템플릿의 생성기 이미지 주소를 함께 갱신했습니다.\n- 이미지 주소는 아래 리뷰어 참고사항에 기록했습니다.\n", 1)
body = body.replace("Closes #", "Closes #" + os.environ["DEPLOY_ISSUE"], 1)
body = body.replace("> 리뷰어가 특히 집중해서 봐야 할 부분이나 배경 맥락을 적어 주세요.", "이미지 주소\n\n" + os.environ["GENERATOR_IMAGE"] + "\n\n이미지 빌드와 smoke 검사는 백엔드 생성기 CD에서 완료했습니다. 이 PR에서는 DAG Python 문법과 git diff --check를 확인했습니다. 실제 GKE 실행은 이미지 갱신 후 확인해야 합니다. 롤백은 이전 이미지 주소로 되돌립니다. 이미지 주소 변경이므로 기존 생성 주기와 건수에 따라 모델 호출 비용이 발생합니다.")
path.write_text(body)
PY
url="$(gh pr create --repo "$repo" --base main --head "$branch" --draft --title "chore: 생성기 이미지 버전 갱신" --body-file "$body" --assignee @me --label feature)"
printf '생성기 이미지 갱신 PR: %s\n' "$url" >> "$GITHUB_STEP_SUMMARY"
