# SendR

A WeTransfer-like file sharing service built with Angular and FastAPI.

## Features

- **File Sharing**: Upload files and share via download links
- **Email Authentication**: Passwordless login with email verification codes
- **Quota Management**: Per-tier upload limits (basic, free, premium)
- **File Expiry**: Automatic file expiration with configurable grace periods
- **Premium Subscriptions**: Higher limits for premium users
- **File Refresh**: Generate new download links for existing files

## Tech Stack

- **Frontend**: Angular 19, SCSS, OpenAPI-generated client
- **Backend**: FastAPI, SQLModel, Alembic (migrations), SQLite
- **Tooling**: uv (Python), bun (JS), ruff (Python linter), oxlint (TS linter)
- **Deployment**: Single Docker image

## Quick Start

### Development

**Backend:**

```bash
cd backend
uv sync
uv run alembic upgrade head
uv run backend
```

Backend email verification behavior is environment-aware:

- `SENDR_ENVIRONMENT=local` logs verification codes instead of sending email
- any other value sends the code using the configured SMTP settings

**Frontend:**

```bash
cd frontend
bun install
bun start
```

### Pre-commit Hooks

This repository versions its Git hook entrypoint in [.githooks/pre-commit](/workspaces/SendR/.githooks/pre-commit).

Enable the tracked hooks once per clone:

```bash
./setup-git-hooks.sh
```

That script installs `pre-commit` with `uv` if needed, sets `core.hooksPath` to `.githooks`, and pre-installs the hook environments.

If you use the devcontainer, this setup runs automatically during container creation.

If you prefer to do it manually:

```bash
uv tool install pre-commit
git config core.hooksPath .githooks
pre-commit install-hooks --config .pre-commit-config.yaml
```

Run the same hooks manually across the full repository:

```bash
pre-commit run --all-files
```

When a commit includes backend API source changes, the pre-commit hook now:

- regenerates [openapi.json](/workspaces/SendR/openapi.json) from the FastAPI app
- regenerates the Angular client in [frontend/src/app/api](/workspaces/SendR/frontend/src/app/api)
- stages those generated changes into the same commit

On frontend-related commits, the pre-commit hook also runs:

- frontend format
- frontend lint
- frontend build

That hook requires `uv`, `bun`, plus either `java` or `docker` on the machine running the commit.

CI also validates that [openapi.json](/workspaces/SendR/openapi.json) and [frontend/src/app/api](/workspaces/SendR/frontend/src/app/api) are not stale by regenerating them in GitHub Actions and failing if that produces a diff.

The hook environments are pinned in [.pre-commit-config.yaml](/workspaces/SendR/.pre-commit-config.yaml), so contributors do not need matching global versions of Ruff, Oxlint, or Oxfmt. `core.hooksPath` itself is still a local Git setting, so each clone needs the one-time `git config` command above.

### Docker

```bash
docker compose up --build
```

Open the frontend at `http://localhost:8080`.

Open the API at `http://localhost:8000`.

This Compose setup builds two images:

- `frontend`: Angular app served by nginx
- `api`: FastAPI backend

In Docker, the frontend nginx container proxies `/api/*` to the backend container so the browser can keep using relative API paths.

For production, put your own reverse proxy or load balancer in front of those two services and route subdomains there:

```bash
app.example.com -> frontend
api.example.com -> api
```

If the frontend and API are on different origins, update `SENDR_ALLOWED_ORIGINS` for the frontend origin and configure the frontend proxy/base URL at your edge.

## API Documentation

When the backend is running, visit:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>

## Tier Limits

| Feature          | Basic  | Free | Premium |
| ---------------- | ------ | ---- | ------- |
| Email required   | Yes    | Yes  | Yes     |
| Files per week   | 3      | 5    | 50      |
| Max file size    | 100 MB | 1 GB | 10 GB   |
| Browse history   | No     | Yes  | Yes     |
| Edit files       | No     | No   | Yes     |
| Retrieve expired | No     | No   | Yes     |

## Project Structure

```text
SendR/
├── backend/           # FastAPI backend
│   ├── src/backend/   # Application source
│   │   ├── routers/   # API endpoints
│   │   ├── models.py  # SQLModel database models
│   │   ├── schemas.py # Request/response schemas
│   │   └── ...
│   ├── alembic/       # Database migrations
│   └── pyproject.toml # Python dependencies & config
├── frontend/          # Angular frontend
│   ├── src/app/
│   │   ├── api/       # Auto-generated OpenAPI client
│   │   ├── pages/     # Page components
│   │   ├── services/  # Angular services
│   │   └── ...
│   └── package.json
├── backend/Dockerfile # Backend image build
├── frontend/Dockerfile# Frontend image build
└── openapi.json       # Generated API spec
```
