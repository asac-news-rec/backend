# OpenRouter 뉴스 생성기 이미지

로컬 Airflow 환경(`generate/local_airflow/`)과 이전 로컬 생성기·출력물
(`generate/local_generate/`)은 `.gitignore`로 제외해 PC에만 보관합니다.
GCP 생성기 이미지에는 아래 Dockerfile에 지정된 소스·CSV·의존성 파일을 사용합니다.
이미지 갱신 보조 스크립트 `.github/scripts/update-generator-image.py`와
`.github/scripts/open-generator-image-pr.sh`는 Git에 포함하며 생성기 CD에서 사용합니다.
업로드 후 pipeline 저장소를 체크아웃하고 두 파일의 이미지 주소를 갱신하는 Draft PR을 생성합니다.

[현재] Python 3.14와 uv를 사용합니다. 루트의 `pyproject.toml`과 `uv.lock`에 정의된 `openrouter` 의존성 그룹을 설치합니다.

기사는 매번 요청한 건수만큼 생성하고, 보관된 일별 JSONL의 고유 기사 수를 기준으로 10건마다 썸네일 한 장을 생성합니다. 1~9번째 기사는 이미지 없이 저장하고 10번째 기사에 이미지를 생성합니다. 날짜가 바뀌어도 누적 순서를 이어가며 같은 실행의 재시도는 기존 기사를 재사용합니다. 이미지 없는 기사의 `image_path`·`image_url`·`image_caption`은 null 또는 생략이며 DB의 `image_url`은 NULL입니다. 본문 모델은 모든 기사에서 `image_prompt`를 생성하되 이미지 API는 열 번째 기사마다 호출합니다.

누적 건수는 동일 출력 루트에 보관된 날짜별 백업 전체로 계산합니다. 실행 간 같은 PVC를 사용해야 하며, 백업을 삭제하거나 출력 루트를 바꾸면 집계 기준도 달라집니다. 출력 루트의 `.articles.lock`으로 동시 생성과 백업 집계를 잠급니다.

백엔드 루트에서 빌드합니다.

```bash
docker build --platform linux/amd64 -f generate/Dockerfile -t news-generator:local .
docker run --rm news-generator:local --help
```

`generate/Dockerfile.dockerignore`는 이 Dockerfile 전용 빌드 제외 설정입니다. 이미지에는 생성기 Python 파일 3개와 CSV 2개를 복사합니다.

사용할 모델 ID는 기사 생성용 `google/gemini-2.5-flash`, 썸네일용 `black-forest-labs/flux.2-klein-4b`입니다. Gemini는 `POST /api/v1/chat/completions`에 JSON Schema를 전달합니다. FLUX는 `POST /api/v1/images`로 16:9 PNG 한 장을 요청하고 `data[0].b64_json`을 디코딩한 뒤 640×360 PNG로 저장합니다.

모델 ID와 API 키를 환경변수에 준비한 다음 기사 1건을 생성합니다. 생성 결과는 호스트의 `news-output` 폴더에 보관합니다.

```bash
mkdir -p news-output
export OPENROUTER_TEXT_MODEL=google/gemini-2.5-flash
export OPENROUTER_IMAGE_MODEL=black-forest-labs/flux.2-klein-4b
docker run --rm \
  -e OPENROUTER_API_KEY \
  -v "$PWD/news-output:/output" \
  news-generator:local \
  --text-model "$OPENROUTER_TEXT_MODEL" \
  --image-model "$OPENROUTER_IMAGE_MODEL" \
  --count 1 --output-root /output
```

실제 생성은 OpenRouter 사용료가 발생합니다. 키는 실행 환경에서 주입합니다. 호출 형식은 [이미지 생성 공식 문서](https://openrouter.ai/docs/guides/overview/multimodal/image-generation)와 [구조화 출력 공식 문서](https://openrouter.ai/docs/guides/features/structured-outputs)를 기준으로 합니다.

DB 적재 시 `--write-db`, `--date`, `--run-id`, `--image-base-url`과 DB 접속 환경변수가 필요합니다. 대상 DB에는 테이블이 사전 준비돼 있어야 합니다.

GKE에서는 `PGPASSWORD_SECRET=projects/final-project-513508/secrets/news-db-password/versions/latest`를 전달합니다. 생성기가 Google 공식 Secret Manager SDK와 ADC 인증으로 비밀번호를 읽어 프로세스의 `PGPASSWORD`에 설정합니다. Pod 서비스 계정의 Workload Identity 연결과 해당 Secret에 대한 `roles/secretmanager.secretAccessor` 권한이 필요합니다. Secret 경로를 지정하면 기존 `PGPASSWORD`보다 우선합니다. 로컬에서는 `PGPASSWORD`를 직접 설정할 수 있습니다. Secret 읽기 실패 시 DB 적재 전에 오류로 종료합니다.

[현재] JSONL·PNG는 지정 폴더에 저장합니다. `--thumbnail-bucket` 또는 `THUMBNAIL_BUCKET`을 지정하면 이미지가 있는 기사에서 PNG를 GCS에 업로드한 뒤 DB에 적재합니다. JSONL 백업은 PVC에 유지합니다.

검증은 이미지 빌드와 `--help` 실행 후 실제 환경에서 생성·저장 순서로 진행합니다. 롤백은 Airflow에서 이전 이미지 버전을 지정합니다. 생성 건수와 실행 주기는 모델 사용료 및 저장 용량에 영향을 줍니다.

## GitHub Actions 이미지 업로드

[현재] 생성기 전용 `generator-ci.yml`의 `Generator image smoke test`가 PR과 main 푸시에서 생성기 이미지를 빌드하고 진입점·모듈·CSV·스키마를 검사합니다. 이 검사는 API 키와 DB 접속 없이 실행합니다.

`generator-cd.yml`은 릴리스 공개 또는 main 브랜치의 Actions → generator-cd → Run workflow로 시작합니다. 해당 커밋의 main 푸시 생성기 CI 성공을 확인한 뒤 이미지를 다시 빌드·검사하고 Artifact Registry에 업로드합니다. CI가 아직 완료되지 않았으면 CI 성공 후 다시 실행합니다.

기존 백엔드 CD와 같은 Actions Variables `GCP_PROJECT`, `AR_REGION`, `AR_REPOSITORY` 및 인증 Secret `GCP_SA_KEY`를 사용합니다. 인증 계정에는 대상 이미지 저장소의 업로드 권한이 필요합니다.

이미지 주소는 `<AR_REGION>-docker.pkg.dev/<GCP_PROJECT>/<AR_REPOSITORY>/news-generator:<커밋SHA>`입니다. Actions 실행 Summary의 `뉴스 생성기 이미지`에서 실제 주소를 확인할 수 있습니다. CD는 `data-ml-pipeline`의 `dags/generate_news.py`에 있는 `GENERATOR_IMAGE`와 `dags/pod_templates/news-generator.yaml`의 생성기 컨테이너 `image`를 같은 주소로 갱신한 Draft PR을 생성합니다. PR 승인·머지 후 기존 git-sync가 Airflow에 전달하며, 자동 머지는 하지 않습니다.

백엔드 Actions Secret `PIPELINE_REPO_TOKEN`을 사용합니다. 토큰에는 대상 저장소의 Contents·Issues·Pull requests 읽기/쓰기 권한이 필요하며 조직 정책에 따라 승인이 필요합니다. 대상 main에는 DAG, Pod 템플릿, PR 양식이 먼저 있어야 합니다. 토큰 등록만으로 대상 파일이 생기지는 않습니다. 같은 이미지 주소가 main에 있으면 변경을 생략하고, 같은 SHA의 갱신 PR이 이미 있으면 해당 PR을 재사용합니다. 토큰 확인이나 PR 생성이 실패해도 앞서 업로드한 이미지는 유지됩니다. 실제 원격 PR 생성과 GKE 실행은 로컬 검증에 포함하지 않습니다.

릴리스 공개 시 기존 Cloud Run CD와 생성기 이미지 업로드가 각각 실행됩니다. 생성기 이미지 업로드만 원하면 main에서 수동 workflow를 사용합니다. 이 workflow의 산출물은 업로드된 이미지이며, Airflow에서 실제 작업을 실행하려면 Pod 템플릿·Secret·저장소 설정을 준비해야 합니다. 모델 API 실제 호출은 Airflow 검증 단계에서 확인합니다.

문제 발생 시 DAG의 이미지 주소를 이전에 검증한 커밋 태그로 되돌립니다. 업로드 시 이미지 보관 비용, CI 실행 시간 및 네트워크 사용이 발생합니다.

OpenRouter 키도 `OPENROUTER_API_KEY_SECRET`에 지정한 Secret Manager 버전 경로를 직접 조회합니다. 경로가 있으면 로컬 환경변수 `OPENROUTER_API_KEY`보다 우선합니다. 제안 경로는 `projects/final-project-513508/secrets/openrouter-api-key/versions/latest`이며 실제 Secret 생성 여부와 이름은 인프라에서 확인해야 합니다. 실행 계정에는 이 Secret의 읽기 권한도 필요합니다.


## 기존 썸네일 버킷 연결

공유받은 기존 경로 규칙에 맞춰 `THUMBNAIL_BUCKET=final-project-513508-news-thumbnails`, `IMAGE_BASE_URL=https://storage.googleapis.com/final-project-513508-news-thumbnails/images`를 사용합니다.

예를 들어 `<output-root>/2026-11-19/images/news-123.png`를 `gs://final-project-513508-news-thumbnails/images/2026-11-19/images/news-123.png`로 업로드합니다. DB URL은 `https://storage.googleapis.com/final-project-513508-news-thumbnails/images/2026-11-19/images/news-123.png`가 됩니다. 최상위 images와 날짜 아래 images는 기존 경로 규칙을 유지한 것입니다.

PNG와 JSONL은 PVC에 먼저 기록합니다. 업로드 실패 시 DB 적재 전에 종료하며, 같은 실행을 재시도하면 백업에서 기존 기사와 PNG를 재사용합니다. 이미 업로드한 객체가 있으면 해시를 비교해 같은 파일임을 확인합니다. 생성기 실행 계정에는 버킷의 images/ 경로 아래 `storage.objects.create`, `storage.objects.get` 권한이 필요합니다. 버킷 공개 읽기 설정은 인프라에서 관리합니다. 첨부받은 운영 설명을 기준으로 경로를 반영했으며 현재 버킷의 공개 설정과 실제 쓰기 권한은 배포 전에 확인해야 합니다.
