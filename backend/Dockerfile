FROM python:3.14.6-slim-bookworm@sha256:4ff4b92a68355dbdb52584ab3391dff8d371a61d4e063468bfd0130e3189c6d9

COPY --from=ghcr.io/astral-sh/uv:0.11.25@sha256:1e3808aa9023d0980e7c15b1fa7c1ac16ff35925780cf5c459858b2d693f01a9 /uv /usr/local/bin/uv

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
