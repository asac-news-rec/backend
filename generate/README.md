# backend

Backend API: recommendation serving and event collection

뉴스 추천 프로젝트의 backend 저장소입니다. 현재 포함된 코드는 `synthetic_news`에서 가져온
기사·썸네일 생성, PostgreSQL 적재용 CLI입니다.
로컬 PostgreSQL용 Docker Compose는 저장소 루트에 있습니다. 뉴스 조회·좋아요·익명 ID 발급 FastAPI는 `../app/`에 있습니다. 추천서버 연결, 사용자 행동 이벤트 수집 API, 생성 Worker의 Docker/Kubernetes 배포 구성은 아직 포함되어 있지 않습니다.

## 포함 파일

| 파일 | 용도 |
| --- | --- |
| `generate_with_thumbnail.py` | Gemma/Ollama 또는 Haiku로 기사·영문 이미지 프롬프트 생성, SDXL로 실사풍 PNG 생성 |
| `load_postgres.py` | 기사 JSONL 검증 및 PostgreSQL upsert |
| `requirements_thumbnail.txt` | 기사·이미지 생성 및 PostgreSQL 적재 의존성 |
| `news_category.csv` | 기사 대분류·중분류 |
| `publisher.csv` | 언론사 52개, 기사마다 무작위 선택 |
| `.gitignore` | 모델 캐시·실행 결과·비밀정보 등 Git 제외 |

## 필요한 프로그램과 모델

| 구성 | 역할 | 준비 방법 |
| --- | --- | --- |
| Python 3.14 | 생성·이미지 처리·DB 적재 코드 실행 | conda 또는 venv 환경 생성 후 의존성 설치 |
| Ollama | 로컬 텍스트 모델을 실행하는 서버 | Ollama 설치 후 실행 |
| Gemma 3 4B | 기사 본문과 영문 이미지 프롬프트 작성 | `ollama pull gemma3:4b` |
| SDXL | 이미지 프롬프트를 받아 썸네일 생성 | 첫 이미지 생성 시 코드가 모델 가중치 다운로드 |
| Diffusers·PyTorch | Python 안에서 SDXL 실행 | `requirements_thumbnail.txt`로 설치 |
| PostgreSQL | 생성된 기사를 DB에 적재할 때 사용 | 루트의 Docker Compose 또는 별도 PostgreSQL 서버 |

**SDXL은 Stable Diffusion XL의 약자이며 Stable Diffusion 계열의 이미지 생성 모델입니다.**
현재 사용하는 모델은 `stabilityai/stable-diffusion-xl-base-1.0`입니다.
Stable Diffusion WebUI, AUTOMATIC1111, ComfyUI는 이 코드 실행에 필요하지 않습니다.
Ollama도 SDXL을 실행하지 않습니다. SDXL은 생성 Python 프로세스에서 실행됩니다.

```text
생성 Python 코드
  ├─ Ollama 서버 → Gemma → 기사 + 영문 이미지 프롬프트
  └─ Diffusers + PyTorch → SDXL → PNG 이미지
                                   ↓
                      날짜별 JSONL + images 폴더
                                   ↓ 별도 load_postgres 실행
                               PostgreSQL
```

## 최초 설치: macOS 로컬 기준

### 1. Python 환경과 라이브러리

아래 경로는 현재 프로젝트 위치입니다. 다른 PC에서는 내려받은 프로젝트 경로로 변경하세요.

```bash
cd /Users/taewonkim/Documents/final_project/backend/generate

# 새 환경이 필요한 경우 한 번만 생성
conda create -n recommand314 python=3.14
conda activate recommand314

python -m pip install -r requirements_thumbnail.txt
```

이미 `recommand314` 환경을 사용 중이면 환경 생성은 생략하고 활성화·패키지 설치만 합니다.
`python -m pip`는 현재 선택한 Python 환경에 패키지를 설치합니다.
Python 패키지 설치만으로 Ollama 프로그램이나 Gemma 모델까지 설치되지는 않습니다.

`recommand_env.yml`은 Python 3.14 Conda 환경 설정이며, 개인 PC 경로는 포함하지 않습니다.
WAS까지 함께 설치하려면 backend 루트에서 `python -m pip install -r requirements.txt`를 실행합니다.
`recommand_pip.txt`는 현재 환경의 전체 버전 스냅샷으로, 학습·분석·Jupyter 패키지까지 포함하므로 일반 실행에 전부 필요한 목록은 아닙니다.
기존 환경에서 `python --version`으로 3.14인지 확인하세요. 환경 파일을 편집하는 것만으로 실행 중인 Python 버전이 바뀌지는 않습니다.

### 2. Ollama 설치·실행과 Gemma 다운로드

[Ollama 공식 다운로드](https://ollama.com/download)에서 macOS용 앱을 설치하고 실행합니다.
새 터미널에서 아래 명령을 실행합니다.

```bash
ollama --version
ollama pull gemma3:4b
ollama list
```

`pull`은 Gemma 모델을 내려받는 명령이며, `list` 결과에 `gemma3:4b`가 표시되면 준비된 것입니다.
Ollama 앱이 서버를 실행 중이면 별도 서버 실행은 필요 없습니다.
앱을 사용하지 않고 터미널에서 서버를 실행하려면 별도 터미널에서 다음 명령을 실행한 채 유지합니다.

```bash
ollama serve
```

이미 서버가 실행 중일 때 다시 실행하면 포트 사용 중 오류가 날 수 있습니다.
기본 접속 주소는 `http://localhost:11434`입니다.

### 3. 기사와 이미지 한 건 생성

```bash
conda activate recommand314
cd /Users/taewonkim/Documents/final_project/backend/generate
python -m generate_with_thumbnail --count 1 --model gemma3:4b
```

첫 실행에서는 기사와 이미지 프롬프트를 작성한 후 SDXL 모델 파일을 Hugging Face에서 다운로드합니다.
이 과정에는 인터넷과 여러 GB의 저장 공간이 필요하며, 다운로드·모델 로드에 시간이 걸릴 수 있습니다.
별도로 SDXL 설치 명령을 실행할 필요는 없습니다. 첫 실행이 끝나면 출력 폴더의 JSONL과 PNG를 확인합니다.

```text
output_with_thumbnail/
  YYYY-MM-DD/
    articles-000001.jsonl
    images/
      thumbnail-000001-000001.png
```

이 명령은 파일 생성까지만 수행합니다. DB 적재와 GCS 업로드를 자동으로 수행하지 않습니다.
DB 적재 방법은 아래 PostgreSQL 적재 절과 [루트 README](../README.md)를 참고하세요.

## 모델 캐시·인터넷·실행 장치

모델 가중치는 모델이 학습한 결과를 담은 대용량 파일입니다. 캐시는 이를 보관해 다음 실행에서 다시 사용하는 저장 공간입니다.

| 대상 | 보관 위치·사용 방식 |
| --- | --- |
| Gemma 등 Ollama 모델 | Ollama가 관리하는 모델 저장소. 설치 여부는 `ollama list`로 확인 |
| SDXL | 코드에서 지정한 `generate/.cache/huggingface/` |
| 생성 결과 | `generate/output_with_thumbnail/`의 JSONL과 이미지 |

모델 캐시는 Git으로 전달되지 않습니다. 새 PC에서는 모델을 다시 다운로드해야 합니다.
캐시가 있으면 해당 가중치를 재사용하지만, 새 프로세스는 모델을 메모리에 다시 로드합니다.
실행 장치를 바꾸면 필요한 가중치 파일이 달라 추가 다운로드가 필요할 수 있습니다.

패키지·모델을 모두 준비하고 Ollama가 로컬에서 실행 중이면 로컬 모델로 생성할 수 있습니다.
SDXL의 Hugging Face 접속을 막고 준비된 캐시만 사용하려면 다음처럼 실행합니다. 필요한 파일이 없으면 실패합니다.

```bash
HF_HUB_OFFLINE=1 python -m generate_with_thumbnail --count 1 --model gemma3:4b
```

`--device auto`가 기본이며 NVIDIA CUDA → Apple MPS → CPU 순으로 사용 가능한 장치를 선택합니다.
Mac Apple Silicon에서는 MPS를 사용합니다. CPU 실행도 가능하지만 이미지 생성이 오래 걸릴 수 있습니다.
Ollama와 SDXL이 메모리를 많이 사용하므로 처음에는 한 건으로 확인하고 다른 작업의 메모리 사용량도 고려하세요.
일반 Linux Docker 컨테이너가 Mac의 MPS를 그대로 사용하는 구조는 아니므로, 현재 macOS 안내는 호스트에서 직접 실행하는 기준입니다.

```bash
# Apple Silicon GPU를 명시적으로 사용
python -m generate_with_thumbnail --count 1 --device mps

# CPU를 명시적으로 사용
python -m generate_with_thumbnail --count 1 --device cpu
```

## 기사·썸네일 생성 옵션

```bash
# 지정 건수 생성. --count:50이 아니라 --count 50
python -m generate_with_thumbnail --count 50 --model gemma3:4b

# 다른 텍스트 모델을 쓰려면 먼저 다운로드
ollama pull qwen3.5:9b
python -m generate_with_thumbnail --model qwen3.5:9b --count 1

# 기존 기사에 이미지만 생성: 원본 유지, 날짜 폴더에 다음 번호 파일 생성
python -m generate_with_thumbnail --input /path/to/articles.jsonl

# 다른 주소의 Ollama 서버 사용
python -m generate_with_thumbnail --count 1 --base-url http://localhost:11434
```

`--input`도 영문 이미지 프롬프트 작성에 텍스트 모델을 사용하므로 Ollama 또는 선택한 API 모델이 필요합니다.
Haiku를 선택하면 Ollama 대신 Anthropic API로 텍스트를 생성합니다. SDXL은 여전히 로컬 Python에서 실행됩니다.
`ANTHROPIC_API_KEY` 환경변수와 인터넷 접속이 필요하며 API 요금이 발생할 수 있습니다.
생성 프로그램은 루트 `.env`를 자동으로 읽지 않습니다. `.env` 자동 읽기는 DB 적재 프로그램의 기능입니다.

### 자주 만나는 오류

| 증상 | 확인할 내용 |
| --- | --- |
| `ollama: command not found` | Ollama 설치 및 새 터미널에서 명령 인식 여부 |
| Ollama 접속 거부 | Ollama 앱 또는 `ollama serve` 실행 여부, 서버 주소 |
| 모델을 찾지 못함 | `ollama list` 확인 후 지정한 이름으로 `ollama pull` |
| SDXL 다운로드 실패 | 인터넷 연결·디스크 여유·캐시 파일 다운로드 상태 |
| 메모리 부족 | 다른 무거운 작업 종료 후 한 건 실행. CPU는 느리고 RAM도 필요 |
| `token repeat limit reached` | 텍스트 모델의 반복 출력으로 생성 중단. 아래 재시도 정책 참고 |
| PostgreSQL 접속 거부 | DB 서버 실행 여부와 루트 `.env`의 호스트·포트 확인 |

- 기사 JSON 형식 오류(필수 tags 누락 등)와 Ollama의 `token repeat limit reached` 생성 중단은 단계별 기본 3회까지 재시도합니다.
  `--max-attempts 5 --retry-delay 2`로 변경할 수 있습니다. 대기 시간은 재시도마다 2배 증가하며 최대 30초입니다.
- 재시도 소진 시 해당 기사 슬롯을 건너뛰고 다음 기사로 진행합니다. 이미지 묘사 실패 시 기사는 보존하고 해당 이미지만 건너뜁니다.
- `--count`는 생성 슬롯 수이므로 실패가 있으면 저장 기사 수가 적을 수 있습니다. 성공한 기사의 이미지는 계속 생성합니다.
- 재시도 대상 생성 오류는 날짜 폴더의 `generation_errors-번호.jsonl`에 기록합니다. 최종 미해결 실패가 있으면 결과를 보존하고 종료 코드 1로 종료합니다.
- 인증·접속 오류나 디스크 저장 실패 등은 위 생성 오류 재시도의 대상이 아닙니다. JSONL의 기존 필드·형식은 유지합니다.

- 텍스트 모델: `gemma3:4b`(기본), `qwen3.5:9b`, `exaone3.5:7.8b`, `haiku`.
- Haiku는 `ANTHROPIC_API_KEY` 환경변수가 필요하며 API 요금이 발생할 수 있습니다.
- Ollama 주소는 `--base-url` 또는 `OLLAMA_BASE_URL`, 기본 `http://localhost:11434`입니다.
- 분류 제한: `--category`, `--subcategory`. 기준일: `--date YYYY-MM-DD`.
- 날짜마다 `output_with_thumbnail/YYYY-MM-DD/` 폴더 하나를 사용합니다. 기본은 실행 시작일(한국 시간), `--date` 지정 시 그 날짜입니다. 실행 도중 자정이 지나도 해당 실행은 시작 날짜를 유지합니다.
- 같은 날짜에 실행할 때마다 `articles-000001.jsonl`, `articles-000002.jsonl`처럼 다음 번호의 새 파일을 만듭니다. 기존 JSONL에 이어 쓰거나 덮어쓰지 않습니다.
- 이미지도 `images/thumbnail-000001-000001.png`(파일 번호-기사 순번)처럼 번호를 붙입니다. 기사 `id`는 기존 UUID 생성 방식을 유지합니다.
- 오류 기록은 `generation_errors-000001.jsonl`처럼 해당 실행 파일 번호를 사용합니다.
- `--input` 이미지 재생성도 다음 번호의 새 JSONL·이미지에 저장합니다. 원본 JSONL과 기사 ID는 유지합니다.
- 기사와 이미지 묘사를 먼저 작성하고, SDXL을 로드해 이미지들을 순차 생성합니다.
- 이미지 모델은 `stabilityai/stable-diffusion-xl-base-1.0`입니다. 충분한 RAM/GPU 메모리가 필요합니다.
- CUDA/MPS는 float16, CPU는 float32를 사용하며 `--device auto|cuda|mps|cpu`로 지정합니다.
- 1024×576에서 생성 후 640×360 PNG로 저장합니다. HTML은 생성하지 않습니다.
- 모델 캐시는 코드에서 `generate/.cache/huggingface`로 지정합니다. 필요한 파일이 이미 있으면 재사용합니다. Xet 비활성화 설정도 코드에 들어 있습니다.
- `image_path`는 JSONL 기준 로컬 상대 경로입니다. 공개 웹 URL이 아닙니다.
- JSONL에 `image_caption`과 `is_synthetic` 표시를 유지하며 `generation`, `thumbnail`, `thumb`는 제외합니다.
- 이미지 실패 시 콘솔 오류와 `image_path=null`을 확인합니다. 자동 재개 기능은 없습니다.

생성 기사는 허구이며 `publisher`의 실제 언론사가 작성한 보도가 아닙니다.
기사 형식 검증은 내용·분류의 의미적 정확성을 보장하지 않습니다.

## PostgreSQL 적재

```bash
python -m pip install -r requirements_thumbnail.txt

# 날짜별 전체 JSONL 검증(DB 쓰기 없음)
python -m load_postgres --date 2026-11-02 --validate-only

# 날짜별 전체 적재
python -m load_postgres --date 2026-11-02 \
  --host localhost --port 5433 --dbname newsdb --user recommend

# 파일 하나만 지정하는 기존 방식도 사용 가능
python load_postgres.py --input /path/to/articles.jsonl --validate-only

# PostgreSQL 서버와 DB·계정은 별도 준비
python load_postgres.py --input /path/to/articles.jsonl \
  --host localhost --port 5433 --dbname newsdb --user recommend
```

`--date`는 파일 저장 폴더의 날짜를 선택합니다(기사 published_at 필터가 아님). 새 날짜 폴더의 `articles-*.jsonl`을 번호순으로 읽습니다. 오류 로그·임시 파일은 제외합니다. 기존 `run-YYYYMMDD-.../articles.jsonl`도 해당 날짜와 일치하면 먼저 읽으며, 기존 폴더를 이동하거나 수정하지 않습니다.
같은 기사 ID가 여러 파일에 있으면 나중에 읽은 파일의 값을 사용해 한 번 upsert합니다. 재생성 이미지 결과를 뒤 번호로 저장했다면 그 결과가 우선합니다. 파일 번호는 데이터 최신성의 절대 보장이 아니므로 오래된 입력을 뒤 번호로 재저장할 때 주의하세요.
생성 중인 새 형식 파일은 적재하지 않고 오류를 냅니다. 생성이 끝난 뒤 실행하세요. 실패로 남은 빈 기사 파일은 건너뛰며, 선택한 파일 중 잘못된 JSON·필수값 오류가 있으면 DB에 쓰기 전에 중단합니다.

프로젝트 루트 backend/.env를 자동으로 읽습니다. 별도 source 명령 없이 실행하면 됩니다.
설정 우선순위는 CLI 옵션 > 기존 환경변수 > .env > 기본값입니다.
비밀번호는 .env·환경변수의 `PGPASSWORD` 또는 `~/.pgpass`로 전달하며 코드·Git에 저장하지 않습니다.
접속 설정에는 `PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`도 사용할 수 있습니다.
적재 실행은 한 트랜잭션에서 아래 테이블을 준비하고 기사만 upsert합니다.

| 테이블 | 생성 컬럼·키 |
|---|---|
| public.news_articles | 기존 기사 19개 컬럼, id 기본키 |
| public.article_likes | reader_id·article_id 복합 기본키, liked_at |
| public.article_like_history | change_id UUID 기본키, reader_id, article_id, action, changed_at |

좋아요 두 테이블의 article_id는 news_articles(id)를 참조합니다. history.action은 like/unlike만 허용합니다.
기사 재적재는 현재 좋아요와 변경 이력을 수정하지 않습니다. 이 적재 CLI는 좋아요 행을 생성하지 않으며,
현재 `../app/repository.py`의 `set_like()`와 API 연결 컨텍스트가 상태 변경과 이력 추가를 같은 트랜잭션으로 수행합니다.
같은 상태 요청에는 이력을 추가하지 않습니다.
--validate-only는 DB 접속·테이블 생성을 수행하지 않습니다.
CREATE TABLE IF NOT EXISTS는 이미 있는 테이블의 정의를 자동 변경하지 않습니다. 기존 스키마가 다르면 별도 변경 SQL이 필요합니다.

기존 DB의 컬럼을 삭제하거나 기존 raw_article을 일괄 정리하는 구문은 적재 경로에서 제거했습니다.

### 로컬 이미지 URL 자동 변환

적재기는 image_url이 없는 기사에 대해 JSONL 위치 + 상대 image_path를 계산한 뒤, --output-root 기준 경로를 이미지 기본 URL에 붙입니다. JSONL 원본과 raw_article은 변경하지 않고 DB의 image_url 컬럼만 변환합니다. 기존 image_url이 있으면 그 값을 유지하고, image_path도 없으면 NULL로 저장합니다.

```bash
# 별도 터미널: output_with_thumbnail을 이미지 공개 루트로 제공
python -m http.server 8001 --bind 127.0.0.1 --directory output_with_thumbnail

# URL 확인만 수행(DB 변경 없음)
python -m load_postgres --date 2026-11-02 --validate-only

# 기본 URL을 명시해 DB 적재
python -m load_postgres --date 2026-11-02 --image-base-url http://localhost:8001

# 환경변수로 설정해도 됨(CLI 옵션이 우선)
export IMAGE_BASE_URL=http://localhost:8001
```

기본값은 http://localhost:8001입니다. 예를 들어 2026-11-02/articles-000001.jsonl의 image_path가 images/thumbnail-000001-000001.png이면 http://localhost:8001/2026-11-02/images/thumbnail-000001-000001.png가 됩니다. 기존 run-... 폴더도 실제 경로를 유지해 URL을 만듭니다. 공백·한글 등은 URL 인코딩합니다.

입력 JSONL이 기본 출력 루트 밖에 있으면 --output-root로 이미지 HTTP 제공 루트를 지정하세요. 루트 밖을 가리키는 image_path는 오류 처리합니다. localhost 주소는 같은 PC 브라우저에서 확인할 때 사용하는 주소입니다.

GCS 이전 시 같은 상대 경로로 이미지를 먼저 업로드하고 --image-base-url을 https://storage.googleapis.com/버킷이름/접두경로 등으로 바꿀 수 있습니다. 이 옵션은 URL 문자열만 구성하며 업로드·공개 권한 설정은 하지 않습니다. 비공개 버킷의 만료되는 서명 URL은 별도 설계가 필요합니다. 기존 image_url은 자동 교체하지 않으므로 이미 로컬 image_url을 넣은 입력 JSON을 GCS 주소로 바꿀 경우 명시적인 데이터 갱신이 필요합니다.

## 추천 학습 샘플

추천 학습 코드는 별도 `../../recommendation_sample/` 폴더의 README.md를 참고하세요.
이 폴더의 통합 의존성에는 CatBoost·pandas 등 추천 학습 전용 패키지를 포함하지 않습니다.

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
- 추천 학습 결과는 `../../recommendation_sample/recommendation_results/`로 이동했습니다.

추천 샘플 자료는 backend 바깥의 recommendation_sample 폴더에서 관리합니다.
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

## 공식 참고 자료

- [Ollama 설치](https://ollama.com/download)
- [Gemma 3 모델 목록](https://ollama.com/library/gemma3)
- [SDXL Base 1.0 모델 설명](https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0)
