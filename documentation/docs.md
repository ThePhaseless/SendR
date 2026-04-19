# SendR – Project Documentation

## Introduction

### Overview

SendR is a file-sharing web application inspired by services such as WeTransfer. The goal of the project was to create a convenient and functional platform that allows users to upload, share, and manage files through download links — while meeting the security requirements defined in the context of the *Cloud Services Security* course.

### Motivation

The idea for SendR originated from a simple observation: existing file-sharing services like WeTransfer, while convenient, have notable limitations in terms of security and control. WeTransfer, for example, allows file sharing without requiring any account, which — while convenient for casual use — makes it difficult to enforce access control, manage quotas, or track usage.

The initial concept aimed to build something *more convenient* than WeTransfer. However, as the project evolved and security requirements were taken into account, the team recognized a fundamental trade-off: convenience and security often pull in opposite directions.

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

### Project Timeline

The project was carried out over approximately three and a half months, from early March 2025 to mid-June 2025. Development of the core application took place first, with cloud deployment planned as the final phase.

## System Architecture

### High-Level Overview

SendR follows a classic client-server architecture, split into two independently deployable services:

- **Frontend** — an Angular single-page application served by an nginx web server
- **Backend** — a Python REST API built with FastAPI

The two services communicate exclusively through a well-defined HTTP API. The frontend never accesses the database directly. In both local development and Docker-based deployments, the frontend nginx instance acts as a reverse proxy, forwarding all `/api/*` requests to the backend service.

> **Architecture Summary**  
> **Frontend** (Angular + nginx) → **/api/\* proxy** → **Backend** (FastAPI) → **Database** (SQLite)

### Frontend

The frontend is a single-page application (SPA) built with Angular 19. It is responsible for all user-facing interactions: uploading files, authenticating via email, browsing upload history, and managing file links.

A notable aspect of the frontend setup is the use of an **auto-generated API client**. The OpenAPI specification is exported from the running FastAPI backend, and the Angular client code is generated from it automatically. This ensures that the frontend and backend are always in sync with respect to request and response shapes, without requiring manual maintenance of API interfaces.

### Backend

The backend is a RESTful API built with **FastAPI**, a modern Python web framework known for its performance and automatic documentation generation. The backend handles:

- User authentication (email-based, passwordless)
- File upload, storage, and retrieval
- Quota enforcement per user tier
- File expiry and link management
- Subscription tier management (Basic, Free, Premium)

Database interactions are handled through **SQLModel**, which combines SQLAlchemy and Pydantic into a single model definition. Database schema migrations are managed with **Alembic**, allowing the schema to evolve over time without data loss.

### Database

The application uses **SQLite** as its database engine. SQLite was chosen for its simplicity and zero-configuration nature, which is well-suited for the scope of this project. It stores all user data, file metadata, and authentication tokens.

### Deployment Model

Both the frontend and backend are packaged as **Docker containers**. Each service has its own `Dockerfile`. This makes the application portable and easy to deploy on any infrastructure that supports containers — including cloud platforms.

## Technology Stack

### Frontend Technologies

| Technology       | Purpose                                               |
| ---------------- | ----------------------------------------------------- |
| Angular 19       | Main frontend framework (SPA)                         |
| TypeScript       | Programming language for the frontend                 |
| SCSS             | Styling                                               |
| OpenAPI Generator| Auto-generates the HTTP client from the backend API spec |
| Bun              | JavaScript runtime and package manager                 |
| nginx            | Serves the frontend and proxies API requests          |

### Backend Technologies

| Technology | Purpose                                          |
| ---------- | ------------------------------------------------ |
| Python     | Programming language for the backend             |
| FastAPI    | Web framework for building the REST API          |
| SQLModel   | ORM combining SQLAlchemy and Pydantic            |
| Alembic    | Database migration management                    |
| SQLite     | Relational database                              |
| uv         | Python package and environment manager           |

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

### Tier-Based Access Control

SendR implements a three-tier user system that controls upload limits and available features:

| Feature               | Basic      | Free       | Premium    |
| --------------------- | ---------- | ---------- | ---------- |
| Email required        | Yes        | Yes        | Yes        |
| Files per week        | 3          | 5          | 50         |
| Max file size         | 100 MB     | 1 GB       | 10 GB      |
| Browse history        | No         | Yes        | Yes        |
| Edit files            | No         | No         | Yes        |
| Retrieve expired files| No         | No         | Yes        |

### File Expiry and Refresh

Files uploaded to SendR are not stored indefinitely. Each file has a configurable expiry period. Users with a Premium tier can retrieve files even after expiry within a grace period, as well as generate new download links for existing files.

### API Documentation

Because the backend is built with FastAPI, interactive API documentation is automatically generated and available at runtime:

- **Swagger UI** — available at `/docs`
- **ReDoc** — available at `/redoc`

## Development Process

### Version Control and Workflow

The project was developed using **Git** with the repository hosted on **GitHub**. All source code, configuration files, and infrastructure definitions are versioned in the same repository, following a monorepo structure.

### Code Quality Automation

A significant effort was put into automating code quality checks. The repository uses **pre-commit hooks** that run automatically before every commit. These hooks perform the following checks:

- **Backend**: Python code is linted and formatted using `ruff`
- **Frontend**: TypeScript code is linted using `oxlint` and formatted automatically
- **API sync check**: If backend API source files are modified, the `openapi.json` specification and the Angular API client are automatically regenerated and staged into the same commit
- **Frontend build**: On frontend-related commits, a build is run to catch compile-time errors early

> **Why This Matters**  
> The automatic regeneration of the API client on every backend change ensures that the frontend is always working against an up-to-date contract. This eliminates an entire class of integration bugs that would otherwise only be caught at runtime.

### Continuous Integration

A **GitHub Actions** CI pipeline runs on every push and pull request. Among other checks, it validates that the `openapi.json` file and the generated Angular client are not stale — by regenerating them and checking whether any diff is produced. If the generated files are out of date, the pipeline fails.

### Dependency Management

Dependencies are kept up to date automatically using **Renovate**, a bot that monitors the repository and opens pull requests whenever a new version of a dependency is available.

### Development Environment

The repository includes a **devcontainer** configuration, allowing developers to work in a fully pre-configured environment using VS Code Dev Containers or GitHub Codespaces. The devcontainer automatically installs all required tools and sets up the pre-commit hooks on first launch.

## Cloud Deployment

> **Work in Progress**  
> This section will be completed once the cloud deployment phase of the project is finalized. The target cloud provider and deployment architecture will be described here.

### Containerization

Both the frontend and backend are already fully containerized using **Docker**. Each service has a dedicated `Dockerfile`:

- `backend/Dockerfile` — builds the FastAPI application image
- `frontend/Dockerfile` — builds the Angular application and packages it with nginx

This containerization means the application is **cloud-ready**: it can be deployed to any container orchestration platform or cloud service that supports Docker images, including AWS ECS, Azure Container Apps, or Google Cloud Run.

### Planned Deployment Architecture

*To be completed.*

### Security Considerations for Cloud Deployment

When deploying to a cloud environment, the following configuration points must be addressed:

- **CORS**: The backend does not allow any cross-origin requests by default. The `SENDR_ALLOWED_ORIGINS` environment variable must be set to the frontend's public URL when deploying to separate origins.
- **SMTP**: A production email server must be configured for the email authentication flow to work.
- **Environment**: `SENDR_ENVIRONMENT` must be set to `production` to enable CAPTCHA and real email delivery.
- **Storage**: SQLite is suitable for small deployments, but a managed relational database service may be considered for production scale.

## Summary

### What Was Achieved

Over the course of the project, the team built a fully functional file-sharing web application from scratch. The application includes a working frontend, a REST API backend, email-based authentication, a tier-based access control system, and a complete containerized deployment setup.

The development process itself was designed with quality in mind: automated linting, pre-commit hooks, continuous integration, and auto-generated API clients all contribute to a codebase that is consistent and maintainable.

### Key Lessons Learned

The most important lesson from this project was the **tension between security and usability**. The original vision was a service more convenient than WeTransfer — but once security requirements were properly considered, mandatory authentication became a necessity. This is a real-world trade-off that any security-conscious application must navigate.

> **Conclusion**  
> SendR demonstrates that it is possible to build a secure, functional, and well-structured file-sharing service using modern open-source technologies. The project served as a practical exercise in full-stack development, security-conscious design, and cloud-ready deployment.

### Future Work

- Complete cloud deployment and document the infrastructure setup
- Migrate from SQLite to a managed database for production
- Add end-to-end encryption for uploaded files
- Implement file scanning for malicious content