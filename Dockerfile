FROM python:3.14-slim
WORKDIR /app

# container에서 docker compose logs로 확인할 때 출력이 지연되지 않도록 함
ENV PYTHONUNBUFFERED=1
# python이 실행되면서 __pycache__/*.pyc파일을 생성하지 않도록 함
# __pycache__/*.pyc: 다음 실행 때 code를 읽는 시간을 줄이는 캐시임. 컨테이너에서는 필요없어서 삭제(필수아님)
ENV PYTHONDONTWRITEBYTECODE=1

# 공식 이미지에서 버전을 고정한 uv 바이너리를 가져온다.
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-cache --no-dev --no-install-project

# CMD와 Compose에서 실행하는 python이 같은 .venv를 사용한다.
ENV PATH="/app/.venv/bin:$PATH"

COPY app/ ./app/
# --host 0.0.0.0(0.0.0.0은 요청을 보내는 상대의 IP가 아니라, WAS가 요청을 받을 자신의 주소를 지정)	컨테이너 밖에서 들어오는 연결도 받을 수 있도록 대기.
# --port 8000	컨테이너 내부의 8000번 포트에서 대기
# 127.0.0.1로 실행하면 해당 컨테이너 내부에서만 접근할 수 있어, 다른 Nginx 컨테이너가 접속할 수 없습니다.
# Nginx → http://api:8000
#              ↓
# Docker가 api 서비스의 IP를 찾아 연결
#              ↓
# WAS가 0.0.0.0:8000에서 수신
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
