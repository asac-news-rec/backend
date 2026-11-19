#!/usr/bin/env bash
# 이미지가 생성기 진입점과 필수 모듈·CSV를 포함하는지 확인합니다.
set -euo pipefail
image="${1:?이미지 주소를 지정하세요}"
docker run --rm "$image" --help
docker run --rm --entrypoint python "$image" -c '
from pathlib import Path
from generate.generate import ROOT, ArticleWithImagePrompt, load_taxonomy, load_publishers
from generate.load_postgres import article_row, upsert_articles
assert load_taxonomy(ROOT / "news_category.csv")
assert load_publishers(ROOT / "publisher.csv")
assert "image_prompt" in ArticleWithImagePrompt.model_json_schema()["properties"]
print("생성기 모듈·스키마·CSV 검사 통과")
'
