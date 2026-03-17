# =============================================================================
# SendR - Single Docker image for Frontend + Backend
# =============================================================================

# Stage 1: Build Angular frontend
FROM oven/bun:latest AS frontend-build

WORKDIR /app/frontend

COPY frontend/package.json frontend/bun.lock ./
RUN bun install --frozen-lockfile

COPY frontend/ ./
RUN bunx ng build --configuration production

# Stage 2: Build Python backend + serve everything
FROM python:3.14-slim AS production

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install backend dependencies
COPY backend/pyproject.toml backend/uv.lock backend/.python-version ./backend/
WORKDIR /app/backend
RUN uv sync --no-dev --frozen

# Copy backend source
COPY backend/src ./src
COPY backend/alembic ./alembic
COPY backend/alembic.ini ./alembic.ini

# Copy built frontend
COPY --from=frontend-build /app/frontend/dist/frontend/browser /app/static

WORKDIR /app

# Create upload directory
RUN mkdir -p /app/uploads

# Set environment variables
ENV SENDR_UPLOAD_DIR=/app/uploads
ENV SENDR_DATABASE_URL=sqlite+aiosqlite:///app/data/sendr.db

# Expose port
EXPOSE 8000

# Run migrations then start server
CMD cd /app/backend && \
    uv run alembic upgrade head && \
    uv run uvicorn backend.app:app --host 0.0.0.0 --port 8000
