# SendR Frontend

This is the Angular client for SendR. It provides the upload, download, dashboard, admin, and subscription views and consumes the FastAPI backend through the generated OpenAPI client in `src/app/api` plus a small set of hand-written services.

## Local Development

Install dependencies and start the dev server from this directory:

```bash
bun install
bun run start
```

`bun run start` runs Angular's dev server on `0.0.0.0`. In `angular.json`, the `serve` target defaults to the `local-dev` configuration, which uses `src/environments/environment.local.ts`. That enables local-only developer UI affordances while keeping API calls relative to `/api`.

The dev server proxy in `proxy.conf.json` forwards `/api` to `http://localhost:8000`. Start the backend separately, for example:

```bash
cd ../backend/src
source ../.venv/bin/activate
SENDR_ENVIRONMENT=local SENDR_DEV_LOGIN_ENABLED=true SENDR_SECRET_KEY=local-dev-secret uvicorn app:app --host 0.0.0.0 --port 8000
```

Use `SENDR_DEV_LOGIN_ENABLED=true` only with `SENDR_ENVIRONMENT=local`. The backend rejects dev login in non-local environments.

## Available Scripts

| Command | Purpose |
| --- | --- |
| `bun run start` | Start the Angular dev server with the default local-dev serve configuration. |
| `bun run build` | Build the production bundle. |
| `bun run watch` | Build continuously with the development build configuration. |
| `bun run test` | Run Karma tests once with watch mode disabled. |
| `bun run test:watch` | Run Karma in watch mode. |
| `bun run lint` | Run oxlint against frontend source. |
| `bun run lint:fix` | Run oxlint with autofix enabled. |
| `bun run format` | Format frontend source with oxfmt. |
| `bun run format:check` | Check formatting without writing changes. |
| `bun run generate-api` | Regenerate the OpenAPI client with Orval. |

## API Client

The generated API client lives in `src/app/api` and is generated from the root `openapi.json`. When backend contracts change, regenerate from the repository root with:

```bash
./scripts/generate-openapi-client.sh
```

or from this directory after `openapi.json` has already been refreshed:

```bash
bun run generate-api
```

Generated client files should stay in the same commit as the backend API change that required them.

## Environment Modes

| File | Used by | Notes |
| --- | --- | --- |
| `src/environments/environment.ts` | Development build fallback | Relative API base and dev tools disabled. |
| `src/environments/environment.local.ts` | `serve:local-dev` | Relative API base and dev tools enabled for local-only workflows. |
| `src/environments/environment.prod.ts` | Production build | Uses the configured production API origin and disables dev tools. |

Local development sends browser requests to `/api` and relies on the Angular proxy. Production builds prefix generated API requests with `environment.prod.ts`; the nginx container also keeps an `/api` reverse proxy for same-origin/container deployments.

## Verification

For frontend-only work, run:

```bash
bun run format:check
bun run lint
bun run build --configuration production --base-href /SendR/
```

For targeted tests, run:

```bash
bun run test -- --watch=false --browsers=ChromeHeadlessNoSandbox --progress=false
```

When a change affects user-visible behavior, also start the dev server and verify the relevant flow in a browser.
