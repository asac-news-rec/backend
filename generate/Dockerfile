FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-cache --only-group openrouter --no-install-project

COPY generate/generate.py generate/article_schema.py generate/load_postgres.py ./generate/
COPY generate/news_category.csv generate/publisher.csv ./generate/

ENTRYPOINT ["python", "-m", "generate.generate"]
