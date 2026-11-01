# backend

Backend API: recommendation serving and event collection

뉴스 추천 프로젝트의 backend 저장소입니다. 현재 포함된 코드는 `synthetic_news`에서 가져온
기사·썸네일 생성, PostgreSQL 적재, CatBoost 추천 학습용 CLI입니다.
HTTP 추천 서빙 API, 사용자 이벤트 수집 API, Docker/Kubernetes 배포 구성은 아직 포함되어 있지 않습니다.

## 포함 파일

| 파일 | 용도 |
| --- | --- |
| `generate_with_thumbnail.py` | Gemma/Ollama 또는 Haiku로 기사·영문 이미지 프롬프트 생성, SDXL로 실사풍 PNG 생성 |
| `load_postgres.py` | 기사 JSONL 검증 및 PostgreSQL upsert |
| `train_recommender.py` | 클릭 예측 학습·시간 분리 평가·사용자별 추천 생성 |
| `news_category.csv` | 기사 대분류·중분류 |
| `publisher.csv` | 언론사 52개, 기사마다 무작위 선택 |
| `recommendation_sample.csv` | 추천 학습 기본 입력. 사용자 5명·노출 100건의 합성 샘플 |
| `requirements.txt` | 기사 작성용 공통 의존성 |
| `requirements-thumbnail.txt` | 공통 의존성과 SDXL 실행 패키지 |
| `requirements-postgres.txt` | DB 적재 패키지 |
| `requirements-recommendation.txt` | CatBoost 학습 패키지 |
| `.gitignore` | 모델 캐시·실행 결과·비밀정보 등 Git 제외 |

## 실행 환경

사용할 conda 환경을 활성화한 뒤 이 저장소의 루트에서 실행합니다.
기존 로컬 검증 환경 이름은 `recommand`이며, 팀원은 자신의 환경을 사용해도 됩니다.
Python 3.12가 기존 검증 기준입니다. conda 환경·인증정보·Ollama 모델은 Git에 포함하지 않습니다.

```bash
conda activate recommand
cd /path/to/backend
```

## 기사·썸네일 생성

```bash
python -m pip install -r requirements-thumbnail.txt

# Ollama 서버가 실행 중이어야 합니다. 모델이 없다면 먼저 받습니다.
ollama pull gemma3:4b

# 기본 텍스트 모델 gemma3:4b, 이미지 모델 SDXL 1.0
python generate_with_thumbnail.py --count 20

# 텍스트 모델을 직접 지정
python generate_with_thumbnail.py --model qwen3.5:9b --count 1

# 기존 기사에 이미지만 생성: 입력 전체 행 처리, 새 출력 폴더 생성
python generate_with_thumbnail.py --input /path/to/articles.jsonl
```

- 텍스트 모델: `gemma3:4b`(기본), `qwen3.5:9b`, `exaone3.5:7.8b`, `haiku`.
- Haiku는 `ANTHROPIC_API_KEY` 환경변수가 필요하며 API 요금이 발생할 수 있습니다.
- Ollama 주소는 `--base-url` 또는 `OLLAMA_BASE_URL`, 기본 `http://localhost:11434`입니다.
- 분류 제한: `--category`, `--subcategory`. 기준일: `--date YYYY-MM-DD`.
- 출력은 `output_with_thumbnail/run-실행시각-식별자/articles.jsonl`과 `images/*.png`입니다.
- 기사와 이미지 묘사를 먼저 작성하고, SDXL을 로드해 이미지들을 순차 생성합니다.
- 이미지 모델은 `stabilityai/stable-diffusion-xl-base-1.0`입니다. 충분한 RAM/GPU 메모리가 필요합니다.
- CUDA/MPS는 float16, CPU는 float32를 사용하며 `--device auto|cuda|mps|cpu`로 지정합니다.
- 1024×576에서 생성 후 640×360 PNG로 저장합니다. HTML은 생성하지 않습니다.
- 모델 캐시는 코드에서 저장소 내부 `.cache/huggingface`로 지정합니다. 기존 SDXL 캐시를 이 경로로 복사했으므로
  동일 모델·가중치는 재다운로드 없이 재사용합니다. Xet 비활성화 설정도 코드에 들어 있습니다.
- `image_path`는 JSONL 기준 로컬 상대 경로입니다. 공개 웹 URL이 아닙니다.
- JSONL에 `image_caption`과 `is_synthetic` 표시를 유지하며 `generation`, `thumbnail`, `thumb`는 제외합니다.
- 이미지 실패 시 콘솔 오류와 `image_path=null`을 확인합니다. 자동 재개 기능은 없습니다.

생성 기사는 허구이며 `publisher`의 실제 언론사가 작성한 보도가 아닙니다.
기사 형식 검증은 내용·분류의 의미적 정확성을 보장하지 않습니다.

## PostgreSQL 적재

```bash
python -m pip install -r requirements-postgres.txt

# DB에 쓰지 않고 입력만 확인
python load_postgres.py --input /path/to/articles.jsonl --validate-only

# PostgreSQL 서버와 DB·계정은 별도 준비
python load_postgres.py --input /path/to/articles.jsonl \
  --host localhost --port 5433 --dbname newsdb --user recommend
```

비밀번호는 `PGPASSWORD` 또는 `~/.pgpass`로 전달하며 코드·Git에 저장하지 않습니다.
접속 설정에는 `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`도 사용할 수 있습니다.
`public.news_articles`를 생성하고 동일한 `id`는 갱신하며, 한 트랜잭션으로 적재합니다.

현재 적재기는 기존 `generation` 컬럼과 `raw_article` 내부의 같은 키를 제거하는 구문도 실행합니다.
실제 서비스 DB에 적용하기 전에 스키마 변경 정책과 실행 권한을 확인해야 합니다.

현재 DB의 이미지 컬럼은 `image_url`입니다. 생성기의 `image_path`를 자동으로 웹 주소로 바꾸지 않습니다.
Cloud Storage 등 이미지 저장소 업로드 및 `image_url` 연결은 후속 구현 대상입니다.

## CatBoost 추천 학습

### 재생성 가능한 개발용 예제

`generate_recommendation_sample.py`는 외부 API 없이 사용자 10명, 가상 기사 40개,
추천 요청 200회(요청당 5개 노출)의 합성 데이터 1,000행을 만듭니다.
기존 `recommendation_sample.csv`와 기존 학습 결과는 유지합니다.

```bash
conda activate recommand
python -m pip install -r requirements-recommendation.txt
python generate_recommendation_sample.py
python train_recommender.py --input sample_data/impressions.csv --output-dir sample_data/results
```

첫 스크립트는 `sample_data/impressions.csv`를 생성하고, 두 번째는 CatBoost로
클릭 확률을 학습한 뒤 이미 클릭한 기사를 제외해 사용자별 상위 10개를 저장합니다.
`--requests 1000 --seed 42`로 노출 5,000건을 재생성할 수 있습니다.

| 컬럼 | 의미 |
| --- | --- |
| `user_id`, `article_id`, `request_id` | 사용자·기사·추천 요청 식별자 |
| `impression_time`, `label_window_end` | 노출 시각과 30분 클릭 관찰 종료 시각 |
| `category`, `publisher`, `device` | 기사 분류·가상 언론사·기기 |
| `user_clicks_7d` | 이전 7일간 관찰이 끝난 노출의 클릭 수 |
| `user_category_click_share_7d` | 이전 7일 클릭 중 해당 분류 비중 |
| `article_impressions_24h`, `article_clicks_24h`, `article_ctr_24h` | 이전 24시간 관찰이 끝난 노출·클릭·클릭률 |
| `clicked` | 학습 정답. 관찰 시간 내 클릭 1, 미클릭 0 |
| `is_synthetic` | 합성 데이터 표시 |

피처는 현재 요청 이전의 관찰 완료 이력으로만 계산합니다. 학습은 시간순 750건,
평가는 이후 250건이며 이후 전체 데이터로 최종 모델을 학습합니다(기본 생성 옵션 기준).
정답은 가상의 분류 선호도로 확률적으로 생성하며 실제 행동 데이터가 아닙니다.
실제 로그에서는 노출과 클릭을 연결하고 관찰 시간이 끝난 노출에만 미클릭 0을 부여해야 합니다.
노출되지 않은 기사를 미클릭으로 간주하지 않습니다.
이 예제는 클릭 예측과 후보 정렬을 보여주며 실제 서비스 추천 품질을 보장하지 않습니다.

```bash
python -m pip install -r requirements-recommendation.txt
python train_recommender.py

# 별도 데이터·결과 위치·추천 개수 지정
python train_recommender.py --input /path/to/impressions.csv \
  --output-dir /path/to/results --top-k 10
```

기본 샘플은 100건이며, 시간 순서로 앞선 75건을 학습하고 이후 25건을 평가합니다.
평가 후 전체 100건으로 최종 모델을 다시 학습합니다. 입력을 바꾸면 분할 건수도 달라집니다.
추천 기준 시각은 샘플의 마지막 label 관찰 종료 시각 다음 1초이며, 실제 현재 시각이 아닙니다.
후보는 입력 CSV에 등장하는 기사이며, 사용자별 기존 클릭 기사를 제외합니다.
사용자 ID·기사 ID·제목·`clicked`는 이 초기 모델의 입력 feature가 아닙니다.

결과는 기본 `recommendation_results/`에 저장합니다. 현재 생성된 샘플 결과도 이 저장소에 포함할 수 있도록 복사했습니다.

- `top10_by_user.csv`: 사용자별 추천과 예측 확률
- `candidate_scores.csv`: 모든 후보·feature·점수
- `holdout_predictions.csv`: 시간 분리 평가 결과
- `metrics.json`: 평가 지표·설정·추천 기준 시각
- `catboost_click_model.cbm`: 전체 데이터로 학습한 모델

합성 샘플은 실행 흐름 검증용이며 실제 사용자 추천 품질을 입증하지 않습니다.
실제 API 서빙과 사용자 행동 수집은 별도로 구현해야 합니다.

## 이번 반영에서 제외한 항목

| 제외 항목 | 이유 |
| --- | --- |
| `docs/` | 학습 문서·PDF 변환 자료. 사용자 요청에 따라 제외 |
| `__pycache__/` | Python 실행 캐시 |
| `.DS_Store` | macOS 폴더 메타데이터 |

원본 `synthetic_news`의 파일은 삭제하거나 변경하지 않았습니다.

## 생성 결과 샘플

사용자 요청으로 기존 결과도 복사했습니다. 원본은 유지합니다.

- `output_with_thumbnail/run-20261030-170636-8ab062/`: 기사 20건과 SDXL PNG 20개
- `recommendation_results/`: 사용자별 Top 10, 전체 후보·평가 예측, 지표, CatBoost 학습 모델

이 두 폴더는 현재 `.gitignore`에서 제외하지 않으므로 Git에 추가할 수 있습니다.
`.DS_Store`는 복사하지 않았습니다. 커밋·push는 별도로 수행합니다.

프로젝트 `.cache/huggingface`는 SDXL 이미지 모델의 다운로드 캐시입니다.
Ollama로 받은 Qwen·Gemma·EXAONE은 이 폴더가 아니라 Ollama의 모델 저장소에서 관리합니다.
CatBoost의 `.cbm` 파일은 다운로드 캐시가 아니라 이 샘플로 직접 학습한 추천 모델입니다.

## 로컬 SDXL 캐시

기존 `synthetic_news/.cache`를 이 저장소의 `.cache`로 복사했습니다.
생성 코드는 자신의 위치를 기준으로 `.cache/huggingface`를 사용하므로 별도 환경변수 설정이 필요 없습니다.
동일한 SDXL fp16 가중치를 사용하는 CUDA/MPS 실행에서 기존 캐시를 재사용합니다.
캐시에 없는 변형·새 버전이나 CPU용 가중치는 추가 다운로드가 필요할 수 있습니다.
네트워크 없이 실행하려면 `HF_HUB_OFFLINE=1 python generate_with_thumbnail.py --count 1`처럼
설정할 수 있습니다. Ollama 서버와 텍스트 모델은 별도로 준비되어 있어야 합니다.
`.cache/`는 `.gitignore`로 제외되어 있으며 Git으로 다른 컴퓨터에 전달되지 않습니다.

## Docker 배포 시 Ollama와 SDXL의 실행 위치

현재 코드 구조에서는 Ollama를 별도 컨테이너로 실행하고, Python 생성기가 실행되는
컨테이너 안에서 Diffusers·PyTorch로 SDXL을 직접 실행할 수 있습니다.
아래는 설계 설명이며, 현재 저장소에는 Dockerfile·Compose 설정이나 웹 API가 구현되어 있지 않습니다.

```text
Docker 실행 환경
  ├─ Ollama 컨테이너
  │    └─ Gemma·Qwen·EXAONE 텍스트 모델 실행
  └─ 생성기 컨테이너
       ├─ Python 기사·이미지 생성 코드
       ├─ Ollama HTTP API로 기사와 영어 이미지 묘사 요청
       └─ Diffusers·PyTorch로 SDXL 이미지 생성
```

Ollama 모델을 Python 생성기 컨테이너에 넣을 필요는 없습니다. 생성기에는 Ollama 호출용
라이브러리와 SDXL 실행 패키지를 설치하고, Ollama 서버에 네트워크로 요청합니다.

### 컨테이너 간 연결과 모델 보관

| 항목 | 구성 예시 |
| --- | --- |
| Ollama 주소 | 같은 Compose 네트워크에서 `OLLAMA_BASE_URL=http://ollama:11434` 설정. `ollama`는 서비스 이름 |
| Ollama 모델 저장 | 공식 Ollama 이미지 기준 `/root/.ollama`에 영속 볼륨 연결 |
| SDXL 캐시 | 생성기 코드가 `/app/generate_with_thumbnail.py`라면 `/app/.cache/huggingface`에 볼륨 또는 bind mount 연결 |
| 생성 결과 | `/app/output_with_thumbnail` 등 출력 경로를 별도 영속 저장소에 연결 |
| GPU | 모델을 실행하는 컨테이너에 GPU 접근과 충분한 메모리 제공 |

컨테이너 안의 `localhost`는 그 컨테이너 자신입니다. 생성기에서 별도 Ollama 컨테이너를
호출할 때 `localhost:11434`를 사용하지 않습니다. 서로 다른 호스트·네트워크에 배포하면
해당 환경에서 접근 가능한 Ollama 주소를 지정해야 합니다.

모델 캐시를 Docker 이미지의 `COPY` 대상으로 포함하지 않고 볼륨으로 관리하는 구성을 권합니다.
향후 Dockerfile을 추가할 때 `.dockerignore`에도 `.cache/`를 넣어 빌드 컨텍스트에서 제외합니다.
`.gitignore`는 Git 제외 규칙이며 Docker 빌드 제외 규칙을 대신하지 않습니다.
기존 backend의 `.cache/huggingface`를 bind mount하면 보유한 가중치를 재사용할 수 있습니다.
Ollama 컨테이너도 별도 볼륨에 모델을 받거나 기존 Ollama 저장소를 연결해야 합니다.

Mac에서 직접 실행할 때 사용하는 MPS 가속이 일반적인 Linux Docker 컨테이너에 그대로
전달되지는 않습니다. 로컬 컨테이너에서는 CPU 실행이 될 수 있습니다.
NVIDIA GPU 서버에서는 호스트 드라이버·컨테이너 런타임 GPU 설정과 GPU용 PyTorch 구성을 확인합니다.
Ollama와 SDXL이 같은 GPU를 사용하면 메모리를 공유하므로 동시 실행·모델 상주 정책도 고려합니다.

### 서비스 운영 권장 구성: 웹 Backend와 생성 Worker 분리

```text
브라우저
  ↓
웹 Backend 컨테이너
  ├─ 기사 조회·사용자 행동 수집·추천 응답
  └─ DB와 이미지 URL 사용

스케줄러 또는 작업 요청
  ↓
생성 Worker 컨테이너
  ├─ Ollama에 기사·이미지 프롬프트 작성 요청
  ├─ SDXL로 이미지 생성
  ├─ Cloud Storage 등 이미지 저장소에 업로드
  └─ 기사 내용과 파일 경로를 DB에 저장

Ollama 컨테이너
  └─ 생성 Worker의 텍스트 생성 요청 처리
```

이미지 생성은 연산·메모리 사용량이 크므로 웹 요청 처리와 분리하면 자원·실패·확장 정책을
각각 관리할 수 있습니다. GPU는 생성 Worker와 Ollama의 모델 실행 요구에 맞춰 배정합니다.
위의 이미지 업로드·자동 DB 적재 연결·스케줄러·웹 API는 앞으로 구현할 영역입니다.
현재는 로컬 파일 생성과 별도 DB 적재 CLI까지 제공됩니다.

하나의 backend repo에서 웹 API와 Worker 코드를 관리하더라도 컨테이너는 각각 실행할 수 있습니다.
repo 개수와 컨테이너 개수를 일치시킬 필요는 없습니다. 현재 생성·적재 CLI는 우선 Worker로
컨테이너화하고, 웹 API는 별도 실행 프로세스로 추가하는 구성이 자연스럽습니다.
