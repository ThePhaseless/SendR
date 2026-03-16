# SendR

A WeTransfer-like file sharing service built with Angular and FastAPI.

## Features

- **File Sharing**: Upload files and share via download links
- **Email Authentication**: Passwordless login with email verification codes
- **Quota Management**: Per-tier upload limits (anonymous, free, premium)
- **File Expiry**: Automatic file expiration with configurable grace periods
- **Premium Subscriptions**: Higher limits for premium users
- **File Refresh**: Generate new download links for existing files

## Tech Stack

- **Frontend**: Angular 19, SCSS, OpenAPI-generated client
- **Backend**: FastAPI, SQLModel, Alembic (migrations), SQLite
- **Tooling**: uv (Python), bun/npm (JS), ruff (Python linter), oxlint (TS linter)
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

**Frontend:**
```bash
cd frontend
npm install
npm start
```

### Docker

```bash
docker build -t sendr .
docker run -p 8000:8000 sendr
```

## API Documentation

When the backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Tier Limits

| Feature | Anonymous | Free | Premium |
|---------|-----------|------|---------|
| Files per week | 3 | 5 | 50 |
| Max file size | 100 MB | 1 GB | 10 GB |
| Edit files | No | No | Yes |
| Retrieve expired | No | No | Yes |

## Project Structure

```
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
├── Dockerfile         # Single image build
└── openapi.json       # Generated API spec
```
