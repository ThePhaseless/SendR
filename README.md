# SendR

SendR is a secure file-sharing application built with Angular and FastAPI. It lets authenticated users upload files, share download links, apply access controls, and manage transfers through tier-based limits.

## Features

- File uploads with individual and grouped download links
- Email-based authentication and session cookies
- Public, password-protected, and email-recipient access modes
- Tier-based upload, expiry, download, password, and recipient limits
- Premium link refresh and expired-file recovery windows
- Admin user and transfer management
- Async malware scanning with a separate scan worker and ClamAV service

## Tech Stack

- **Frontend:** Angular 21, TypeScript, SCSS, Bun, OpenAPI-generated client, nginx
- **Backend:** FastAPI, SQLModel, Alembic, uv, SQLite for local development, PostgreSQL for live deployment
- **Storage:** local upload directories for development; DigitalOcean Spaces for live object storage
- **Infrastructure:** Docker images, Kubernetes manifests, Terraform for DigitalOcean infrastructure, GitHub Actions, pre-commit, Renovate

## Quick Start

### Backend

```bash
cd backend
uv sync
uv run alembic upgrade head
SENDR_ENVIRONMENT=local SENDR_SECRET_KEY=local-dev-secret uv run uvicorn src.app:app --host 0.0.0.0 --port 8000
```

Local mode prints verification codes to the backend log and relaxes CAPTCHA checks for development. Dev login endpoints are still closed unless both flags are set:

```bash
SENDR_ENVIRONMENT=local SENDR_DEV_LOGIN_ENABLED=true SENDR_SECRET_KEY=local-dev-secret uv run uvicorn src.app:app --host 0.0.0.0 --port 8000
```

Production-like environments (`dev`, `staging`, and `production`) require explicit secrets, SMTP or Resend email delivery, ALTCHA HMAC configuration, Spaces credentials, and `SENDR_VIRUS_SCANNING_ENABLED=true`.

### Frontend

```bash
cd frontend
bun install
bun run start
```

The Angular dev server defaults to the `local-dev` serve configuration from [frontend/angular.json](frontend/angular.json). It keeps API requests relative to `/api`, and [frontend/proxy.conf.json](frontend/proxy.conf.json) forwards those requests to `http://localhost:8000`.

Frontend production builds use [frontend/src/environments/environment.prod.ts](frontend/src/environments/environment.prod.ts) for the browser API origin. The nginx container also keeps an `/api` reverse proxy, configured by the runtime `API_URL` environment variable, for same-origin/container deployments.

## Verification

Backend checks:

```bash
cd backend
uv run pytest
```

Frontend checks:

```bash
cd frontend
bun run format:check
bun run lint
bun run build --configuration production --base-href /SendR/
```

Frontend targeted tests:

```bash
cd frontend
bun run test -- --watch=false --browsers=ChromeHeadlessNoSandbox --progress=false
```

## API Client

The root [openapi.json](openapi.json) file is generated from the FastAPI app and feeds the Angular client in [frontend/src/app/api](frontend/src/app/api). Regenerate both after backend API contract changes:

```bash
./scripts/generate-openapi-client.sh
```

CI fails if regeneration produces a diff, so backend API changes and generated frontend client updates should be committed together.

## Git Hooks

Enable the repository hooks once per clone:

```bash
./setup-git-hooks.sh
```

The tracked hook entrypoint is [.githooks/pre-commit](.githooks/pre-commit). It can regenerate OpenAPI client files for backend API changes and runs frontend format, lint, and build checks for frontend-related commits. The hook environments are configured in [.pre-commit-config.yaml](.pre-commit-config.yaml).

Run all hooks manually with:

```bash
pre-commit run --all-files
```

## Docker And Deployment

Each service has its own image:

```bash
docker build -t sendr-api ./backend
docker build -t sendr-frontend ./frontend
```

For a local container run, provide backend runtime settings and the frontend upstream API URL explicitly:

```bash
docker run -p 8000:8000 sendr-api
docker run -p 8080:8080 -e API_URL=http://host.docker.internal:8000 sendr-frontend
```

The live deployment uses [k8s/overlays/live](k8s/overlays/live) and Terraform under [terraform](terraform). The production topology includes:

- `sendr-backend` API pods
- `sendr-scan-worker` worker pods
- a separate ClamAV service
- PostgreSQL for relational data
- DigitalOcean Spaces for upload payloads
- Traefik and DNS records for `sendr.email`, `www.sendr.email`, and `api.sendr.email`

Terraform and Kubernetes deployment details live in [terraform/README.md](terraform/README.md), [terraform/SETUP.md](terraform/SETUP.md), and [terraform/ENVIRONMENTS_GUIDE.md](terraform/ENVIRONMENTS_GUIDE.md).

## Async Malware Scanning

When malware scanning is enabled, run three separate runtime roles:

- SendR API process
- SendR scan worker process
- ClamAV daemon or container

The API and worker use the same backend image and must share the same database, storage backend, upload/quarantine directories for local disk deployments, Spaces settings for object storage deployments, and ClamAV endpoint settings.

Typical backend role commands are:

```bash
uv run uvicorn src.app:app --host 0.0.0.0 --port 8000
uv run python src/scan_worker.py
```

ClamAV stays outside the backend image so virus definitions can update without rebuilding SendR.

## API Documentation

When the backend is running locally, visit:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>

## Tier Limits

| Feature                | Temporary | Free | Premium   |
| ---------------------- | --------- | ---- | --------- |
| Email required         | Yes       | Yes  | Yes       |
| Files per week         | 3         | 5    | Unlimited |
| Max file size          | 100 MB    | 1 GB | 10 GB     |
| Browse history         | No        | Yes  | Yes       |
| Edit files             | No        | No   | Yes       |
| Retrieve expired files | No        | No   | Yes       |

## Documentation

- [documentation/docs.md](documentation/docs.md) - project architecture and operating notes
- [documentation/flow-diagram.md](documentation/flow-diagram.md) - workflow sequence diagrams
- [documentation/UMLClassDiagrams](documentation/UMLClassDiagrams) - focused class and schema diagrams
- [documentation/owasp-audit-2026-05-17.md](documentation/owasp-audit-2026-05-17.md) - security review and remediation notes

## Project Structure

```text
SendR/
├── backend/                 # FastAPI backend, Alembic migrations, tests
│   ├── src/                 # Application source
│   ├── tests/               # Backend tests
│   └── pyproject.toml       # Backend dependencies and tooling
├── frontend/                # Angular frontend
│   ├── src/app/api/         # Generated OpenAPI client
│   ├── src/app/components/  # Shared UI components
│   ├── src/app/pages/       # Routed pages
│   └── package.json         # Frontend scripts and dependencies
├── documentation/           # Architecture, security, and diagram docs
├── k8s/                     # Kubernetes base and live overlay
├── scripts/                 # OpenAPI, migration, and helper scripts
├── terraform/               # DigitalOcean infrastructure
└── openapi.json             # Generated API contract
```
