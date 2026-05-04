# SendR – Project Documentation

## Authors

| Name                    | Student ID |
| ----------------------- | ---------- |
| Franciszek Przybyłowski | s223346    |
| Jakub Orchowski         | s223281    |
| Kamil Pizon             | s223434    |
| Filip Obuchowicz        | s223421    |

## Contents

- [Introduction](#introduction)
- [System Architecture](#system-architecture)
- [Technology Stack](#technology-stack)
- [Key Features](#key-features)
- [Environment Configuration](#environment-configuration)
- [Development Process](#development-process)

## Introduction

### Overview

SendR is a file-sharing web application inspired by services such as WeTransfer. The goal of the project was to create a convenient and functional platform that allows users to upload, share, and manage files through download links — while meeting the security standards.

> **Key Design Decision**
> The most significant decision made during the project was to **shift from a convenience-first approach to a security-first approach**. This meant introducing mandatory user authentication, even at the cost of the frictionless experience that services like WeTransfer are known for. A user now must authenticate via email before uploading or managing files.

This decision shaped the entire architecture of the application: authentication, tier-based access, quota enforcement, and file expiry are all consequences of prioritizing a secure environment over anonymous access.

### Project Goals

The primary objectives of the project were:

- Build a functional file-sharing service with a modern web interface
- Implement a secure, passwordless authentication system based on email verification
- Enforce per-user upload limits and file expiry policies
- Package the application for containerized deployment using Docker
- Deploy the application to a cloud environment

## System Architecture

### High-Level Overview

SendR follows a classic client-server architecture, split into two independently deployable services:

- **Frontend** — an Angular single-page application served by an nginx web server
- **Backend** — a Python REST API built with FastAPI

The two services communicate exclusively through a well-defined HTTP API. The frontend never accesses the database directly. In both local development and Docker-based deployments, the frontend nginx instance acts as a reverse proxy, forwarding all `/api/*` requests to the backend service.

> **Architecture Summary**
> **Frontend** (Angular + nginx) → **/api/\* proxy** → **Backend** (FastAPI) → **Database** (SQLite)

### Frontend

The frontend is a single-page application (SPA) built with Angular 21. It is responsible for all user-facing interactions: uploading files, authenticating via email, browsing upload history, and managing file links.

A notable aspect of the frontend setup is the use of an **auto-generated API client**. The OpenAPI specification is exported from the running FastAPI backend, and the Angular client code is generated from it automatically. This ensures that the frontend and backend are always in sync with respect to request and response shapes, without requiring manual maintenance of API interfaces.

### Backend

The backend is a RESTful API built with **FastAPI**, a modern Python web framework known for its performance and automatic documentation generation. The backend handles:

- User authentication (email-based, passwordless)
- File upload, storage, and retrieval
- Quota enforcement per user tier
- File expiry and link management
- Subscription tier management (Temporary, Free, Premium)

Database interactions are handled through **SQLModel**, which combines SQLAlchemy and Pydantic into a single model definition. Database schema changes are managed with **Alembic** migrations.

### Database

The application uses **SQLite** as its database engine. SQLite was chosen for its simplicity and zero-configuration nature, which is well-suited for the scope of this project. It stores all user data, file metadata, and authentication tokens.

### Deployment Model

Both the frontend and backend are packaged as **Docker containers**. Each service has its own `Dockerfile`. This makes the application portable and easy to deploy on any infrastructure that supports containers — including cloud platforms.

## Technology Stack

### Frontend Technologies

| Technology        | Purpose                                                  |
| ----------------- | -------------------------------------------------------- |
| Angular 21        | Main frontend framework (SPA)                            |
| TypeScript        | Programming language for the frontend                    |
| SCSS              | Styling                                                  |
| OpenAPI Generator | Auto-generates the HTTP client from the backend API spec |
| Bun               | JavaScript runtime and package manager                   |
| nginx             | Serves the frontend and proxies API requests             |

### Backend Technologies

| Technology | Purpose                                 |
| ---------- | --------------------------------------- |
| Python     | Programming language for the backend    |
| FastAPI    | Web framework for building the REST API |
| SQLModel   | ORM combining SQLAlchemy and Pydantic   |
| Alembic    | Database migration management           |
| SQLite     | Relational database                     |
| uv         | Python package and environment manager  |

### Tooling and Infrastructure

| Tool           | Purpose                                     |
| -------------- | ------------------------------------------- |
| Docker         | Containerization of both services           |
| GitHub Actions | Continuous integration (CI) pipeline        |
| pre-commit     | Automated code quality checks before commit |
| ruff           | Python linter and formatter                 |
| oxlint         | TypeScript/JavaScript linter                |
| Renovate       | Automated dependency updates                |

## Key Features

### Email-Based Authentication

SendR uses a **passwordless authentication** system. Instead of traditional username/password login, users provide their email address and receive a one-time verification code. This approach eliminates the risk of weak or reused passwords while keeping the login experience simple.

In production mode, verification codes are sent via SMTP. During local development, codes are printed directly to the server log to avoid the need for an email server setup.

### File Sharing

The core feature of SendR is file upload and sharing. After authenticating, users can upload files which are then accessible via unique download links. The system supports file expiry, after which links become invalid and files are eventually purged.

### CAPTCHA Protection

To prevent automated abuse of the authentication and upload endpoints, SendR integrates CAPTCHA verification. CAPTCHA is enabled by default in production mode (SENDR_ENVIRONMENT=production) and is relaxed in local development mode (SENDR_ENVIRONMENT=local) to streamline the development workflow.

### Tier-Based Access Control

SendR implements a three-tier user system that controls upload limits and available features:

| Feature                | Temporary | Free | Premium |
| ---------------------- | --------- | ---- | ------- |
| Email required         | Yes       | Yes  | Yes     |
| Files per week         | 3         | 5    | 50      |
| Max file size          | 100 MB    | 1 GB | 10 GB   |
| Browse history         | No        | Yes  | Yes     |
| Edit files             | No        | No   | Yes     |
| Retrieve expired files | No        | No   | Yes     |

### File Expiry and Refresh

Files uploaded to SendR are not stored indefinitely. Each file has a configurable expiry period. Users with a Premium tier can retrieve files even after expiry within a grace period, as well as generate new download links for existing files.

### Upload Quota Management

The system tracks upload usage per user on a rolling weekly basis. When a user reaches their tier's weekly upload limit, further transfers are rejected until quota resets. This ensures fair resource usage across all accounts.

### API Documentation

Because the backend is built with FastAPI, interactive API documentation is automatically generated and available at runtime:

- **Swagger UI** — available at `/docs`
- **ReDoc** — available at `/redoc`

## Environment Configuration

SendR uses environment variables to control runtime behaviour. The table below documents all supported variables.

| Variable                | Default           | Description                                                                                                          |
| ----------------------- | ----------------- | -------------------------------------------------------------------------------------------------------------------- |
| `SENDR_ENVIRONMENT`     | `production`      | Set to `local` to enable dev login shortcuts and disable CAPTCHA. Use `production` for real deployments.             |
| `SENDR_DEV_MODE`        | `false`           | Enables dev-only backend routes when set to `true`. Never enable in production.                                      |
| `SENDR_ALLOWED_ORIGINS` | (none)            | Comma-separated list or JSON array of allowed CORS origins. Required when frontend and API are on different origins. |
| SMTP settings           | —                 | SMTP host, port, and credentials required for production email delivery. Not needed in local mode.                   |
| `API_URL` (frontend)    | `http://api:8000` | Points the nginx reverse proxy to the backend container. Set when running frontend Docker image.                     |

> **💡 In local development mode (`SENDR_ENVIRONMENT=local`), verification codes are printed to the server log instead of being sent by email, and CAPTCHA verification is relaxed.**

## Development Process

### Version Control and Workflow

The project was developed using Git with the repository hosted on GitHub. All source code, configuration files, and infrastructure definitions are versioned in the same repository, following a monorepo structure.

### Quick Start

#### Backend Quick Start

```bash
cd backend
uv sync
uv run alembic upgrade head
SENDR_ENVIRONMENT=local uv run uvicorn src.app:app --host 0.0.0.0 --port 8000
```

#### Frontend Quick Start

```bash
cd frontend
bun install
bun run start
```

#### Docker Quick Start

```bash
docker build -t sendr-api ./backend
docker build -t sendr-frontend ./frontend
docker run -p 8000:8000 sendr-api
docker run -p 8080:8080 -e API_URL=http://sendr-api:8000 sendr-frontend
```
