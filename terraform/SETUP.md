# SendR Live Deployment Setup

This guide describes the single live DigitalOcean deployment for SendR.

## Architecture

- One DOKS cluster runs the backend, frontend, and Traefik.
- One managed PostgreSQL cluster stores application data.
- One DigitalOcean Spaces bucket stores uploaded files.
- One Terraform remote state backend stores the live infrastructure state.
- GitHub Actions deploys only the `live` environment.

The live configuration currently preserves existing DigitalOcean resource names with `resource_suffix = "dev"`. This is intentional: it lets the repository expose one live deployment without recreating the working cluster, database, VPC, or Spaces bucket.

## One-Time Manual Resources

Terraform uses a remote S3-compatible backend, so the state bucket must exist before Terraform can run.

1. Create a DigitalOcean Spaces bucket in `fra1` for Terraform state.
2. Update `terraform/environments/live/backend.conf` if the bucket name changes.
3. Add `sendr.email` in DigitalOcean Networking -> Domains.
4. Point the domain registrar nameservers to DigitalOcean.
5. Verify the sending domain in Resend and add the Resend DNS records in DigitalOcean.

## Required GitHub Secrets

Only **two** repository secrets are required. All other secrets live in encrypted files inside the repository.

Add these in Settings -> Secrets and variables -> Actions:

- `SOPS_AGE_KEY`: the CI Age private key. SOPS uses it to decrypt every other secret.
- `DO_TOKEN`: DigitalOcean API token with write access (used by `doctl` and the Terraform DO provider).

## Encrypted Files

| File | Purpose |
|------|---------|
| `k8s/overlays/live/secrets.enc.yaml` | Kubernetes Secret for the backend app |
| `terraform/environments/live/terraform.tfvars.enc.json` | Terraform variables (sensitive + non-sensitive) |
| `terraform/environments/live/backend.enc.env` | S3 backend credentials for Terraform state |

Edit an encrypted file locally:

```bash
sops k8s/overlays/live/secrets.enc.yaml
```

Ensure `SOPS_AGE_KEY_FILE` points to your Age private key, e.g.:
```bash
export SOPS_AGE_KEY_FILE="$(pwd)/.sops/keys.txt"
```

## Deployment

Manual deployment:

```bash
gh workflow run deploy-k8s.yml --repo ThePhaseless/SendR --ref main
```

The Terraform workflow validates configuration only. Cloud changes are made by the deploy workflow. Automatic cloud changes stay gated until the repository variable `SENDR_AUTO_DEPLOY_ENABLED` is set to `true`. With that variable enabled, pushes to `main` can apply Terraform and deploy Kubernetes after validation and image publishing.

## Local Operator Commands

Static Terraform validation:

```bash
cd terraform
mise x terraform@latest -- terraform fmt -check -recursive
mise x terraform@latest -- terraform init -backend=false -no-color
mise x terraform@latest -- terraform validate -no-color
```

Live manifest render:

```bash
kubectl kustomize k8s/overlays/live
```

Kubernetes diagnostics after deployment:

```bash
kubectl get pods -n sendr
kubectl rollout status deployment/sendr-backend -n sendr
kubectl rollout status deployment/sendr-frontend -n sendr
kubectl logs -l app=sendr-backend -n sendr -f
```

## Data Migration

For local-to-live data migration, run backend migration tools with live database and Spaces credentials supplied through environment variables. Keep `SENDR_ENVIRONMENT=production` for live application runtime and `SENDR_ENVIRONMENT=local` only for local development.
