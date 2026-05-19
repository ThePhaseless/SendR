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
- **Backend**: FastAPI, SQLModel, Alembic migrations, SQLite
- **Tooling**: uv (Python), bun (JS runtime and package manager), ruff (Python linter), oxlint (TS linter)
- **Deployment**: Separate backend and frontend images deployed to one live Kubernetes environment

## Quick Start

### Development

**Backend:**

```bash
cd backend
uv sync
uv run alembic upgrade head
SENDR_ENVIRONMENT=production uv run uvicorn src.app:app --host 0.0.0.0 --port 8000
```

The backend now defaults to production-safe behavior:

- `SENDR_ENVIRONMENT=production` keeps CAPTCHA enabled, sends verification codes via the configured SMTP server, and disables dev-only routes
- `SENDR_ENVIRONMENT=local` is an explicit local-dev opt-in that logs verification codes to the terminal instead of sending email and relaxes CAPTCHA verification
- `SENDR_DEV_LOGIN_ENABLED=true` must be set alongside `SENDR_ENVIRONMENT=local` before the backend exposes `/api/dev/login/*`

**Frontend:**

```bash
cd frontend
bun install
bun start
```

`bun start` now serves the frontend with the production configuration by default.

If you explicitly want local-only developer conveniences such as dev login buttons and frontend CAPTCHA bypass, use:

```bash
bun run start:local-dev
```

Both frontend entrypoints use the same relative `/api` base path. During local Angular development, `/api/*` is proxied to `http://localhost:8000`. In Docker, nginx proxies `/api/*` to the backend container.

### Pre-commit Hooks

This repository versions its Git hook entrypoint in [.githooks/pre-commit](/workspaces/SendR/.githooks/pre-commit).

Enable the tracked hooks once per clone:

```bash
./setup-git-hooks.sh
```

That script installs `pre-commit` with `uv` if needed, sets `core.hooksPath` to `.githooks`, and pre-installs the hook environments.

If you use the devcontainer, this setup runs automatically during container creation.

The devcontainer uses Bun instead of Node.js for the frontend CLI path and persists the `uv` and `bun` package caches across rebuilds using Docker volumes to keep subsequent builds faster.

If you prefer to do it manually:

```bash
uv tool install pre-commit
chmod +x .githooks/pre-commit
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

That hook requires `uv` and `bun` on the machine running the commit.

CI also validates that [openapi.json](/workspaces/SendR/openapi.json) and [frontend/src/app/api](/workspaces/SendR/frontend/src/app/api) are not stale by regenerating them in GitHub Actions and failing if that produces a diff.

The hook environments are defined in [.pre-commit-config.yaml](/workspaces/SendR/.pre-commit-config.yaml). Ruff still runs from its pinned pre-commit environment, while the frontend format and lint hooks run from the repository's Bun-managed dependencies in [frontend/package.json](/workspaces/SendR/frontend/package.json). `core.hooksPath` itself is still a local Git setting, so each clone needs the one-time `git config` command above.

If commits bypass the hook entirely, first check that Git is pointing at `.githooks` and that [.githooks/pre-commit](/workspaces/SendR/.githooks/pre-commit) is executable.

### Docker

Each service has its own Dockerfile and is built/deployed as a separate container:

```bash
docker build -t sendr-api ./backend
docker build -t sendr-frontend ./frontend
```

The frontend image uses a relative API origin in [frontend/src/environments/environment.prod.ts](frontend/src/environments/environment.prod.ts). Local development uses the Angular dev-server proxy from [frontend/proxy.conf.json](frontend/proxy.conf.json), and the production nginx container proxies `/api/*` to the backend through its runtime `API_URL` environment variable:

```bash
docker run -p 8000:8000 sendr-api
docker run -p 8080:8080 sendr-frontend
```

For the live Kubernetes deployment, GitHub Actions renders [k8s/overlays/live](k8s/overlays/live) and sets the frontend `API_URL` to the in-cluster backend service.

By default, the backend does not allow any cross-origin browser frontend origins. `SENDR_ALLOWED_ORIGINS` can be provided either as a JSON array or as a comma-separated list when you intentionally deploy the frontend and API on different origins.

### Async Scan Topology

If malware scanning is enabled, run three separate runtime roles:

- the SendR API process
- the SendR scan worker process
- a separate ClamAV daemon that updates its own signatures independently of the backend image

The API and worker should use the same backend image and point at the same database and storage backend. For local-disk deployments that means the same clean upload directory and quarantine upload directory. For Spaces-backed deployments, queued files live in object storage until the worker downloads a temporary copy for scanning. The application does not start the worker automatically from the API process.

Minimum shared state for the API and worker:

- `SENDR_DATABASE_URL`
- `SENDR_UPLOAD_DIR`
- `SENDR_UPLOAD_QUARANTINE_DIR`
- `SENDR_SPACES_ACCESS_KEY`, `SENDR_SPACES_SECRET_KEY`, `SENDR_SPACES_BUCKET_NAME`, and `SENDR_SPACES_REGION` when object storage is enabled
- `SENDR_VIRUS_SCANNING_ENABLED=true`
- the same ClamAV endpoint, usually `SENDR_CLAMAV_HOST` and `SENDR_CLAMAV_PORT` or a shared `SENDR_CLAMAV_UNIX_SOCKET`

Typical backend process commands inside the backend container are:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
python src/scan_worker.py
```

The important operational rule is that ClamAV stays outside the backend image. That lets virus definitions update on their own schedule without rebuilding or redeploying the SendR application image.

The Kubernetes production manifests now deploy this topology directly with `sendr-backend`, `sendr-scan-worker`, and a pinned `sendr-clamav` service. Production configuration is expected to keep `SENDR_VIRUS_SCANNING_ENABLED=true`.

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
