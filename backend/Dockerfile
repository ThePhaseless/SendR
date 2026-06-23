FROM python:3.14.6-slim-bookworm@sha256:a70519002c49552ea0a853de47599cf40479b001bd7a624f1112eaf44dcaccc7

COPY --from=ghcr.io/astral-sh/uv:0.11.24@sha256:99ea34acedc870ba4ad11a1f540a1c04267c9f30aadc465a94406f52dfda2c36 /uv /usr/local/bin/uv

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
