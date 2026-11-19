"""업로드된 생성기 이미지 주소를 pipeline 저장소의 두 설정 파일에 반영합니다."""

import ast
import os
from pathlib import Path
import re


image = os.environ["GENERATOR_IMAGE"]
if not re.fullmatch(r"[a-z0-9.-]+-docker\.pkg\.dev/[a-z0-9_-]+/[a-z0-9_-]+/news-generator:[0-9a-f]{40}", image):
    raise ValueError("커밋 SHA가 포함된 생성기 이미지 주소가 필요합니다.")

dag = Path("dags/generate_news.py")
pod = Path("dags/pod_templates/news-generator.yaml")

dag_text, dag_count = re.subn(
    r'^GENERATOR_IMAGE = "[^"\n]+"$',
    f'GENERATOR_IMAGE = "{image}"',
    dag.read_text(),
    flags=re.MULTILINE,
)
pod_text, pod_count = re.subn(
    r'^(\s+image: )\S+/news-generator:\S+$',
    lambda match: match.group(1) + image,
    pod.read_text(),
    flags=re.MULTILINE,
)
if dag_count != 1 or pod_count != 1:
    raise ValueError("DAG 또는 Pod 템플릿의 생성기 이미지 설정을 찾지 못했습니다.")
ast.parse(dag_text)
dag.write_text(dag_text)
pod.write_text(pod_text)
