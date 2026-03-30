FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --no-dev --frozen

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN mkdir -p /app/uploads /app/data

ENV SENDR_UPLOAD_DIR=/app/uploads
ENV SENDR_DATABASE_URL=sqlite+aiosqlite:///app/data/sendr.db
ENV PYTHONPATH=/app/src

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
