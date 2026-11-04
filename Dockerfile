FROM python:3.14-slim
WORKDIR /app

# container에서 docker compose logs로 확인할 때 출력이 지연되지 않도록 함
ENV PYTHONUNBUFFERED=1
# python이 실행되면서 __pycache__/*.pyc파일을 생성하지 않도록 함
# __pycache__/*.pyc: 다음 실행 때 code를 읽는 시간을 줄이는 캐시임. 컨테이너에서는 필요없어서 삭제(필수아님)
ENV PYTHONDONTWRITEBYTECODE=1

COPY app/requirements.txt ./requirements.txt

# --no-cache-dir : package는 설치하되 다운로드한 설치파일 등의 pip캐시는 보관하지 않는다
# 이미지에 불필요한 캐시가 들어가 용량이 커지는 것을 줄임
RUN python -m uv pip install -no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]