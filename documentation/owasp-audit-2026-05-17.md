# OWASP Security Review for SendR

Date: 2026-05-17

## Scope

This review maps the main technologies in this repository to the latest relevant OWASP material fetched from official OWASP pages during this review, rather than relying only on model knowledge.

Technology mapping used in this report:

- FastAPI backend -> OWASP API Security Top 10 2023
- Angular frontend -> OWASP Top 10 2025
- Angular client-side specifics -> OWASP Top 10 Client-Side Security Risks project page, used only as a supplementary lens because the official OWASP page still presents a candidate list rather than a finalized released edition

Official OWASP sources fetched during the review:

- <https://owasp.org/www-project-api-security/>
- <https://owasp.org/API-Security/editions/2023/en/0x11-t10/>
- <https://owasp.org/www-project-top-ten/>
- <https://owasp.org/Top10/2025/>
- <https://owasp.org/www-project-top-10-client-side-security-risks/>

## How This Was Checked

1. Pulled the latest official OWASP category lists from owasp.org.
2. Reviewed the security-critical code paths manually.
3. Searched the codebase for risky patterns such as `localStorage`, `sessionStorage`, `innerHTML`, `bypassSecurityTrust*`, `eval`, `new Function`, query-string secrets, raw external fetches, and shell execution sinks.
4. Verified the current repo state with build/tests:
   - Backend: `uv run pytest` -> 77 passed
   - Frontend: `bun run format:check && bun run lint && bun run build --configuration production --base-href /SendR/ && bun run test -- --watch=false --browsers=ChromeHeadlessNoSandbox --progress=false` -> all checks passed

Key files reviewed:

- [backend/src/app.py](../backend/src/app.py)
- [backend/src/config.py](../backend/src/config.py)
- [backend/src/security.py](../backend/src/security.py)
- [backend/src/rate_limit.py](../backend/src/rate_limit.py)
- [backend/src/errors.py](../backend/src/errors.py)
- [backend/src/routers/auth.py](../backend/src/routers/auth.py)
- [backend/src/routers/dev.py](../backend/src/routers/dev.py)
- [backend/src/routers/admin.py](../backend/src/routers/admin.py)
- [backend/src/routers/files.py](../backend/src/routers/files.py)
- [backend/src/models.py](../backend/src/models.py)
- [backend/src/schemas.py](../backend/src/schemas.py)
- [backend/src/virus_scanner.py](../backend/src/virus_scanner.py)
- [backend/Dockerfile](../backend/Dockerfile)
- [frontend/src/app/services/auth.service.ts](../frontend/src/app/services/auth.service.ts)
- [frontend/src/app/interceptors/auth.interceptor.ts](../frontend/src/app/interceptors/auth.interceptor.ts)
- [frontend/src/app/interceptors/api-error.interceptor.ts](../frontend/src/app/interceptors/api-error.interceptor.ts)
- [frontend/src/app/guards/auth.guard.ts](../frontend/src/app/guards/auth.guard.ts)
- [frontend/src/app/guards/admin.guard.ts](../frontend/src/app/guards/admin.guard.ts)
- [frontend/src/app/pages/download/download.component.ts](../frontend/src/app/pages/download/download.component.ts)
- [frontend/src/app/components/header/header.component.ts](../frontend/src/app/components/header/header.component.ts)
- [frontend/src/index.html](../frontend/src/index.html)
- [frontend/nginx.conf](../frontend/nginx.conf)
- [frontend/Dockerfile](../frontend/Dockerfile)
- [frontend/package.json](../frontend/package.json)

## Executive Summary

Overall posture improved after remediation.

What is clearly good:

- Session auth is cookie-based and HttpOnly on the backend, with CSRF protection in place.
- The Angular app does not store auth tokens in `localStorage` or `sessionStorage`.
- Password hashing uses Argon2.
- Object and function level authorization in the backend are generally well enforced.
- Download-slot consumption is handled atomically at the database layer.
- Docker images are pinned and run as non-root.

Remaining findings after the fixes applied in this session:

- Angular/Nginx deployment is still missing standard browser security headers and CSP.
- Client-side logging and alerting are still minimal.

## Implemented Fixes

### Fix 1: Protected download secrets moved out of query parameters

How it was implemented:

- Removed query-string secret support from file info, file download, group info, group download, and recipient-stats endpoints in [backend/src/routers/files.py](../backend/src/routers/files.py).
- Standardized protected-download access on the existing `X-Access-Token` header path already used by the Angular download flow.
- Updated backend tests in [backend/tests/test_multi_access.py](../backend/tests/test_multi_access.py) so the contract is enforced by tests, not only by code review.

Why it was implemented:

- Query-string secrets are operationally risky because they can leak into browser history, logs, screenshots, copied links, and support tooling.
- The frontend had already moved to the safer header-based pattern, so keeping the old query-string path only preserved risk without providing meaningful value.

### Fix 2: Download throttling added for file and group downloads

How it was implemented:

- Added a dedicated `download_rate_limiter` and `DOWNLOAD_RATE_LIMIT_PER_MINUTE` setting in [backend/src/rate_limit.py](../backend/src/rate_limit.py) and [backend/src/config.py](../backend/src/config.py).
- Enforced the limiter in the single-file and group download handlers in [backend/src/routers/files.py](../backend/src/routers/files.py).
- Added regression coverage in [backend/tests/test_multi_access.py](../backend/tests/test_multi_access.py) to verify that repeated downloads now return `429` after the configured threshold.

Why it was implemented:

- Max-download counters protect business rules, but they do not stop short-burst abuse, bandwidth exhaustion, or repeated scraping attempts.
- A dedicated download limiter reduces OWASP API4 exposure without changing the existing authentication flow.

## Implemented Remediations

### Remediation 1: Dev login now requires explicit local opt-in

How it was implemented:

- Added `DEV_LOGIN_ENABLED` with default `false` and validation rules in [backend/src/config.py](../backend/src/config.py).
- Mounted the dev router only when both `SENDR_ENVIRONMENT=local` and `SENDR_DEV_LOGIN_ENABLED=true` are set in [backend/src/app.py](../backend/src/app.py).
- Kept the route-level fail-closed check in [backend/src/routers/dev.py](../backend/src/routers/dev.py), updated config tests in [backend/tests/test_config.py](../backend/tests/test_config.py), and clarified the behavior in [documentation/docs.md](../documentation/docs.md) and [frontend/src/app/components/header/header.component.ts](../frontend/src/app/components/header/header.component.ts).

Why it was implemented:

- A dev-login endpoint is an intentional auth bypass, so relying only on `ENVIRONMENT=local` was too soft as a safety boundary.
- Requiring an explicit second flag makes the feature fail closed by default and reduces the chance of accidental exposure during misconfiguration.

### Remediation 2: Runtime third-party icon dependency removed

How it was implemented:

- Removed the external Google Fonts stylesheet from [frontend/src/index.html](../frontend/src/index.html).
- Added a local `@font-face` definition in [frontend/src/styles.scss](../frontend/src/styles.scss) backed by the bundled font asset in [frontend/public/assets/fonts/material-symbols-outlined.woff2](../frontend/public/assets/fonts/material-symbols-outlined.woff2).

Why it was implemented:

- This removes a runtime dependency on a third-party origin for core UI rendering.
- It also makes future CSP rollout easier because the app no longer needs external style or font origins just for Material Symbols.

## Implemented Migrations

### Migration 1: API contract migrated to header-only protected-download access

How it was implemented:

- Regenerated [openapi.json](../openapi.json) after removing query-string secret support from the backend.
- Regenerated the Angular API client under [frontend/src/app/api](../frontend/src/app/api) so generated frontend types and endpoints match the backend contract.
- Updated tests to exercise the new header-only access path.

Why it was implemented:

- Security fixes are incomplete if the OpenAPI description and generated client still advertise the old, weaker contract.
- Keeping the spec and generated client synchronized prevents documentation drift and accidental reintroduction of the deprecated access pattern.

### Migration 2: Database and persisted data

How it was implemented:

- No Alembic migration and no data migration were applied.

Why no schema migration was needed:

- The implemented changes affected request handling, runtime configuration, generated client code, and static frontend assets.
- They did not require new tables, new columns, data backfills, or persistence-layer changes.

## Intentionally Not Applied in App Code

- Browser security headers and CSP in [frontend/nginx.conf](../frontend/nginx.conf), because you asked to skip items that should be handled at the reverse-proxy or edge layer rather than hardcoded in the app.
- Client-side telemetry and alerting, because there is no monitoring backend or agreed observability pipeline in this repository, so adding a local-only logger would not fully close the finding.

## FastAPI Review

Benchmark used: OWASP API Security Top 10 2023.

| OWASP API 2023 item                                   | Vulnerable? | What was checked                                                                                                                                                                                                                                                                                                                                                                                                                                                                     | Verdict                                                                                                                  |
| ----------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------ |
| API1: Broken Object Level Authorization               | No          | File and group access go through `_verify_access`, owner checks, and per-group credential checks in [backend/src/routers/files.py](../backend/src/routers/files.py). Admin routes require [backend/src/security.py](../backend/src/security.py).                                                                                                                                                                                                                                     | No direct BOLA issue found.                                                                                              |
| API2: Broken Authentication                           | No          | Session cookies are HttpOnly and CSRF-protected in [backend/src/security.py](../backend/src/security.py) and [backend/src/app.py](../backend/src/app.py). Auth endpoints are rate limited in [backend/src/routers/auth.py](../backend/src/routers/auth.py). File access secrets are now header-only in [backend/src/routers/files.py](../backend/src/routers/files.py).                                                                                                              | No broken-authentication issue was confirmed after remediation.                                                          |
| API3: Broken Object Property Level Authorization      | No          | Response models are explicit in [backend/src/schemas.py](../backend/src/schemas.py), and the code uses typed SQLModel/Pydantic flows rather than mass assignment shortcuts.                                                                                                                                                                                                                                                                                                          | No obvious property-level overexposure issue found.                                                                      |
| API4: Unrestricted Resource Consumption               | Partial     | Upload size, weekly quota, and max-download limits exist in [backend/src/config.py](../backend/src/config.py), [backend/src/routers/auth.py](../backend/src/routers/auth.py), and [backend/src/routers/files.py](../backend/src/routers/files.py). Auth and downloads are rate limited in [backend/src/rate_limit.py](../backend/src/rate_limit.py).                                                                                                                                 | Application-level abuse resistance is improved, but the limiter is still per-process rather than shared across replicas. |
| API5: Broken Function Level Authorization             | No          | Admin routes depend on `get_admin_user` in [backend/src/routers/admin.py](../backend/src/routers/admin.py). Owner-only mutations verify ownership in [backend/src/routers/files.py](../backend/src/routers/files.py).                                                                                                                                                                                                                                                                | No broken function-level authorization issue found in normal runtime mode.                                               |
| API6: Unrestricted Access to Sensitive Business Flows | No          | Upload/download business rules include quotas, expiry windows, max-download logic, and optional Altcha on upload in [backend/src/routers/files.py](../backend/src/routers/files.py).                                                                                                                                                                                                                                                                                                 | No major business-flow bypass was confirmed.                                                                             |
| API7: Server Side Request Forgery                     | No          | No user-controlled remote fetch flow was found. ClamAV integration in [backend/src/virus_scanner.py](../backend/src/virus_scanner.py) is local/configured, not driven by attacker-provided URLs.                                                                                                                                                                                                                                                                                     | No SSRF sink was identified.                                                                                             |
| API8: Security Misconfiguration                       | No          | Production secret validation exists in [backend/src/config.py](../backend/src/config.py). CORS is explicit in [backend/src/app.py](../backend/src/app.py). Dev login now requires explicit opt-in in [backend/src/config.py](../backend/src/config.py), [backend/src/app.py](../backend/src/app.py), and [backend/src/routers/dev.py](../backend/src/routers/dev.py). Trusted proxy handling matters for rate limiting in [backend/src/rate_limit.py](../backend/src/rate_limit.py). | No active misconfiguration issue was confirmed in the app defaults after remediation.                                    |
| API9: Improper Inventory Management                   | No          | Explicit routers are mounted in [backend/src/app.py](../backend/src/app.py), OpenAPI exists in repo root, and dev-only functionality is not mounted outside local mode.                                                                                                                                                                                                                                                                                                              | No strong inventory-management gap found in the code reviewed.                                                           |
| API10: Unsafe Consumption of APIs                     | No          | The backend does not meaningfully consume untrusted third-party APIs from attacker-controlled input.                                                                                                                                                                                                                                                                                                                                                                                 | No unsafe API-consumption issue found.                                                                                   |

### FastAPI Residual Risk

1. Download throttling is still process-local

   Evidence:
   - [backend/src/rate_limit.py](../backend/src/rate_limit.py)

   Why it matters:
   - The current limiter is useful for single-instance deployments.
   - If the service is scaled horizontally, a shared limiter such as Redis would be needed for consistent enforcement across replicas.

### FastAPI Conclusion

The FastAPI backend is not showing a broken-authentication or broken-authorization failure in its main flows. The app-level issues identified in the first pass were fixed; the main remaining backend caveat is that download throttling is still per-process.

## Angular Review

Primary benchmark used: OWASP Top 10 2025.

Why this benchmark was chosen:

- OWASP Top 10 2025 is the latest officially released OWASP Top 10 for web applications.
- The dedicated OWASP client-side project page is useful, but the fetched official page still presents a candidate list rather than a finalized release.

| OWASP 2025 item                             | Vulnerable? | What was checked                                                                                                                                                                                                                                                                                                                               | Verdict                                                                                                      |
| ------------------------------------------- | ----------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| A01: Broken Access Control                  | No          | Route guards in [frontend/src/app/guards/auth.guard.ts](../frontend/src/app/guards/auth.guard.ts) and [frontend/src/app/guards/admin.guard.ts](../frontend/src/app/guards/admin.guard.ts), plus server-side enforcement in the backend.                                                                                                        | No client-side access-control flaw was found; real enforcement remains on the backend.                       |
| A02: Security Misconfiguration              | Yes         | [frontend/nginx.conf](../frontend/nginx.conf) does not set CSP, HSTS, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, or Permissions-Policy.                                                                                                                                                                                         | This remains the clearest frontend finding, but it was intentionally left for edge/reverse-proxy management. |
| A03: Software Supply Chain Failures         | No          | Dependencies are locked in [frontend/package.json](../frontend/package.json) and `bun.lock`, images are pinned in [frontend/Dockerfile](../frontend/Dockerfile), and Material Symbols are now bundled locally via [frontend/public/assets/fonts](../frontend/public/assets/fonts) and [frontend/src/styles.scss](../frontend/src/styles.scss). | No direct supply-chain failure was confirmed in the app after remediation.                                   |
| A04: Cryptographic Failures                 | No          | Angular does not persist auth tokens in web storage. Session state is derived from the backend in [frontend/src/app/services/auth.service.ts](../frontend/src/app/services/auth.service.ts).                                                                                                                                                   | No direct client-side crypto handling flaw was found.                                                        |
| A05: Injection                              | No          | No use of `innerHTML`, `bypassSecurityTrust*`, `eval`, or `new Function` was found in app source. Angular templates and HttpClient usage look conventional.                                                                                                                                                                                    | No direct Angular injection/XSS sink was found in source.                                                    |
| A06: Insecure Design                        | No          | Session-based auth, CSRF header injection in [frontend/src/app/interceptors/auth.interceptor.ts](../frontend/src/app/interceptors/auth.interceptor.ts), guarded routes, and server-verified session refresh.                                                                                                                                   | Overall design is sound.                                                                                     |
| A07: Authentication Failures                | No          | Auth state is session-based, requests use `withCredentials`, and the app avoids browser-readable token persistence.                                                                                                                                                                                                                            | No client-side auth-storage failure was found.                                                               |
| A08: Software or Data Integrity Failures    | Partial     | The stack uses pinned Docker bases, a lockfile, and locally bundled icon fonts. CSP/nonced asset policy is still not enforced at the Nginx edge layer.                                                                                                                                                                                         | App-level asset integrity improved, but edge browser policy remains intentionally deferred.                  |
| A09: Security Logging and Alerting Failures | Partial     | User-facing API errors are normalized in [frontend/src/app/interceptors/api-error.interceptor.ts](../frontend/src/app/interceptors/api-error.interceptor.ts), but no client telemetry, tamper detection, or alerting pipeline is visible in the frontend code reviewed.                                                                        | Operational visibility is limited.                                                                           |
| A10: Mishandling of Exceptional Conditions  | No          | Session expiry, banned-account handling, and download failure handling exist in [frontend/src/app/interceptors/api-error.interceptor.ts](../frontend/src/app/interceptors/api-error.interceptor.ts) and [frontend/src/app/pages/download/download.component.ts](../frontend/src/app/pages/download/download.component.ts).                     | Error handling exists and is reasonably controlled.                                                          |

### Supplementary Angular Client-Side Checks

Supplementary lens used: OWASP Top 10 Client-Side Security Risks project page.

What was specifically checked against that client-side lens:

- Broken client-side access control -> route guards exist, and server enforcement remains authoritative
- DOM-based XSS -> no dangerous DOM sinks found in app source
- Sensitive data stored client-side -> no auth tokens in `localStorage` or `sessionStorage`
- Lack of third-party origin control -> Material Symbols are now bundled locally, so this specific runtime dependency was removed
- Not using standard browser security controls -> confirmed gap because security headers/CSP are missing in Nginx
- Client-side logging and monitoring failures -> limited client telemetry visible

### Angular Findings

1. Missing browser security headers and CSP

   Evidence:
   - [frontend/nginx.conf](../frontend/nginx.conf)
   - [frontend/src/index.html](../frontend/src/index.html)

   Why it matters:
   - Without CSP, the app relies mainly on Angular framework protections and good coding discipline, not browser-enforced policy.
   - Without `X-Frame-Options` or `frame-ancestors`, clickjacking protection is missing.
   - Without `X-Content-Type-Options`, MIME sniffing protection is missing.
   - Without HSTS, transport hardening is weaker at the edge.

2. Client-side monitoring is thin

   Evidence:
   - [frontend/src/app/interceptors/api-error.interceptor.ts](../frontend/src/app/interceptors/api-error.interceptor.ts)

   Why it matters:
   - The app handles user-facing errors, but nothing visible here sends security-relevant client events to monitoring or alerting.

### Angular Conclusion

The Angular code itself looks disciplined: no storage-token smell, no obvious DOM-XSS sink, and session handling is aligned with a cookie-based backend. After remediation, the remaining frontend weakness is mainly browser hardening at the edge, not the Angular component code.

## Supporting Tech Notes

### Nginx

- Main weakness in the reviewed deployment path.
- Presently acts as a proxy and static host, but without standard hardening headers.

### Docker

- Good baseline.
- Both [backend/Dockerfile](../backend/Dockerfile) and [frontend/Dockerfile](../frontend/Dockerfile) use pinned base images.
- Backend container runs as non-root.
- Frontend runtime uses `nginx-unprivileged`.

## Final Verdict

### Are we vulnerable?

FastAPI:

- No major broken-authentication or broken-authorization vulnerability was confirmed in the core app flows.
- No active app-level finding from the original backend pass remains unresolved.
- The only backend caveat left is that download throttling is still per-process for multi-instance deployments.

Angular:

- No direct Angular XSS/token-storage issue was confirmed.
- Yes, still vulnerable at the browser-hardening layer because the deployed frontend lacks standard security headers and CSP.
- The previous third-party icon-font dependency was removed during remediation.

## Priority Remediation

1. Add frontend security headers in [frontend/nginx.conf](../frontend/nginx.conf):
   - `Content-Security-Policy`
   - `Strict-Transport-Security`
   - `X-Frame-Options` or CSP `frame-ancestors`
   - `X-Content-Type-Options`
   - `Referrer-Policy`
   - `Permissions-Policy`

2. If the backend will run on multiple replicas, back [backend/src/rate_limit.py](../backend/src/rate_limit.py) with a shared store such as Redis instead of process memory.

3. Add real client-side security telemetry only after choosing an actual monitoring backend and alerting workflow.
