# SendR Project Rules

These rules apply to the whole repository. Use [frontend/AGENTS.md](frontend/AGENTS.md) for Angular-specific guidance.

## Security Baseline

- Default to production-safe behavior. Local-only routes and features must fail closed outside explicit local development mode.
- Browser authentication must use HttpOnly session cookies. Do not persist bearer tokens in localStorage, sessionStorage, or other JavaScript-readable stores.
- Backend error payloads should use stable machine-readable codes with user-facing messages instead of relying on raw string matching.
- Quota checks, download-limit checks, and similar counters must be enforced atomically. Avoid check-then-act patterns that can be raced.
- Trust proxy headers only from configured trusted proxies.
- Password hashing must use an allowed modern algorithm such as Argon2, bcrypt, or scrypt. Keep old verification paths only during explicit migration windows.

## Backend Rules

- Prefer explicit FastAPI contracts: response models, structured errors, and Annotated dependencies for touched endpoints.
- Keep environment parsing strict and typed where practical. Production secrets must be provided explicitly rather than falling back to committed defaults.
- Do not expose dev-only routers in production builds.
- Keep existing tests and clients passing when changing auth contracts, but move the browser path to cookie-based sessions.

## Frontend Rules

- Treat auth state as session-based. Derive login state from the current backend session rather than stored tokens.
- When backend error codes exist, branch on codes instead of English text.
- For Angular components touched in a change, prefer OnPush and signal-driven state unless the existing file is already using another established pattern that would make the change unsafe in the current scope.

## Secret Management

All application and infrastructure secrets are encrypted with [SOPS](https://getsops.io/) using [Age](https://age-encryption.org/) keys and committed to the repository.

### Encrypted files

| File | Purpose |
|------|---------|
| `k8s/overlays/live/secrets.enc.yaml` | Kubernetes Secret for the backend app |
| `terraform/environments/live/terraform.tfvars.enc.json` | Terraform variables (sensitive + non-sensitive) |
| `terraform/environments/live/backend.enc.env` | S3 backend credentials for Terraform state |

### Bootstrap secrets in GitHub Actions

Only two repository secrets remain in GitHub:

- `SOPS_AGE_KEY` — the CI Age private key. Required to decrypt every other secret.
- `DO_TOKEN` — DigitalOcean API token (used by `doctl` and the Terraform DO provider).

### Adding a team member

1. The new member generates a keypair inside the repo:
   ```bash
   age-keygen -o .sops/keys.txt
   ```
2. They send their public key to the repo admin.
3. Admin runs:
   ```bash
   ./scripts/add-sops-recipient.sh age1...
   ```
   This updates `.sops.yaml` and re-encrypts all files.
4. Commit and push.

### Editing encrypted files

```bash
# Edit in your default editor (re-encrypts on save)
sops k8s/overlays/live/secrets.enc.yaml

# Decrypt to stdout
sops -d terraform/environments/live/terraform.tfvars.enc.json
```

Ensure `SOPS_AGE_KEY_FILE` points to your Age private key, e.g.:
```bash
export SOPS_AGE_KEY_FILE="$(pwd)/.sops/keys.txt"
```

### Local development

Local dev secrets stay in `backend/.env` (gitignored). Each developer manages their own. Do not commit plaintext `.env` files.

## Delivery Rules

- Production Docker images must run as a non-root user.
- Pin Docker bases and GitHub Actions to immutable versions or SHAs for production paths.
- Keep deployment gated on the same blocker-validation jobs that protect the main branch.

## Verification

- Backend: `cd /workspaces/SendR/backend && uv run pytest`
- Frontend: `cd /workspaces/SendR/frontend && bun run format:check && bun run lint && bun run build --configuration production --base-href /SendR/`
- Frontend targeted tests: `cd /workspaces/SendR/frontend && bun run test -- --watch=false --browsers=ChromeHeadlessNoSandbox --progress=false`
- Manual verification must cover login, refresh, logout, admin access, and protected download flows after auth changes.
