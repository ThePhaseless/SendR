FROM python:3.14.6-slim-bookworm@sha256:a70519002c49552ea0a853de47599cf40479b001bd7a624f1112eaf44dcaccc7

COPY --from=ghcr.io/astral-sh/uv:0.11.23@sha256:d0a0a753ab981624b49c97abc98821c1c09f4ca69d1ef5cee69c501be3d88479 /uv /usr/local/bin/uv

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app/src
ENV SENDR_DATABASE_URL=sqlite+aiosqlite:///app/data/sendr.db
ENV SENDR_UPLOAD_DIR=/app/uploads

COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --no-dev --frozen

COPY src ./src
COPY alembic ./alembic
COPY alembic.ini ./alembic.ini

RUN groupadd --system sendr \
	&& useradd --system --gid sendr --home-dir /app --create-home --shell /usr/sbin/nologin sendr \
	&& mkdir -p /app/uploads /app/data \
	&& chown -R sendr:sendr /app

USER sendr:sendr

EXPOSE 8000

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
