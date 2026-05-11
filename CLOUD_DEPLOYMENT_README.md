# SendRR Cloud Deployment Guide

## Overview

SendRR deployment to DigitalOcean Kubernetes (DOKS) using:
- **Terraform 1.11+** for infrastructure provisioning
- **3 Kubernetes clusters** (dev, staging, prod)
- **GHCR** (GitHub Container Registry) for container images
- **GitHub App** (`sendrr-ghcr-bot`) for authenticating to private GHCR
- **Kustomize** for managing environment-specific configurations
- **Traefik** with Let's Encrypt for TLS (bez Helma)
- **GitHub Actions** for CI/CD

## Architecture

```
GitHub Actions ──► GHCR (thephaseless/sendr/backend, thephaseless/sendr/frontend)
                        │
         ┌──────────────┼──────────────┐
         │              │              │
         ▼              ▼              ▼
    Dev Cluster   Staging Cluster   Prod Cluster
    (DOKS)         (DOKS)           (DOKS)
```

## Prerequisites

1. **AWS CLI** with `digitalocean` profile for S3 backend:
   ```bash
   aws configure --profile digitalocean
   # Enter DO Spaces access key and secret
   export AWS_PROFILE=digitalocean
   ```

2. **Terraform 1.11+** installed:
   ```bash
   terraform --version
   ```

3. **kubectl 1.30+** installed:
   ```bash
   kubectl version --client
   ```

4. **Doctl** installed for DigitalOcean CLI:
   ```bash
   doctl account get
   ```

5. **Docker** for local builds (optional)

---

## Step 1: Configure GitHub Secrets

Add these secrets to your GitHub repository:

**Path:** Repository → Settings → Secrets and variables → Actions → New repository secret

| Secret | Type | Description | How to Get |
|--------|------|-------------|------------|
| `GH_APP_ID` | Text | GitHub App ID (number) | GitHub → Settings → Developer settings → GitHub Apps → sendrr-ghcr-bot → App ID |
| `GH_APP_PRIVATE_KEY` | Text | Base64-encoded private key | GitHub App → Private keys → Generate → base64 |
| `DEV_DO_TOKEN` | Text | DO PAT for dev environment | DO API → Tokens → Create |
| `STAGING_DO_TOKEN` | Text | DO PAT for staging environment | DO API → Tokens → Create |
| `PROD_DO_TOKEN` | Text | DO PAT for prod environment | DO API → Tokens → Create |
| `AWS_ACCESS_KEY_ID` | Text | DO Spaces access key | DO Spaces → Settings → Access Keys |
| `AWS_SECRET_ACCESS_KEY` | Text | DO Spaces secret key | DO Spaces → Settings → Access Keys |
| `DEV_KUBECONFIG` | Text | Base64-encoded kubeconfig | `base64 ~/.kube/do-dev-cluster.yaml \| tr -d '\n'` |
| `STAGING_KUBECONFIG` | Text | Base64-encoded kubeconfig | `base64 ~/.kube/do-staging-cluster.yaml \| tr -d '\n'` |
| `PROD_KUBECONFIG` | Text | Base64-encoded kubeconfig | `base64 ~/.kube/do-prod-cluster.yaml \| tr -d '\n'` |

### Getting GH_APP_PRIVATE_KEY

1. Go to GitHub App `sendrr-ghcr-bot` settings:
   - https://github.com/settings/apps/sendrr-ghcr-bot

2. Generate private key (if not exists):
   - Scroll to "Private keys" section
   - Click "Generate a private key"
   - GitHub will download a `.pem` file

3. Convert to base64:

   **Linux/Mac:**
   ```bash
   base64 -i private-key.pem | tr -d '\n'
   ```

   **Windows PowerShell:**
   ```powershell
   [Convert]::ToBase64String([System.IO.File]::ReadAllBytes("C:\path\to\private-key.pem"))
   ```

4. Add as `GH_APP_PRIVATE_KEY` secret in GitHub

### DO Personal Access Token Creation

1. Go to DigitalOcean Console → API → Tokens
2. Click "Generate New Token"
3. Name it (e.g., `sendr-dev-token`)
4. Select scopes: `write`
5. Copy the token immediately (shown only once)
6. Repeat for each environment (dev, staging, prod)

---

## Step 2: Terraform - Create Infrastructure

### Quick Reference:

```bash
cd terraform
export AWS_PROFILE=digitalocean

# Destroy Dev
terraform destroy -var-file="environments/dev.tfvars"
# Type 'yes' when prompted

# Destroy Staging
terraform destroy -var-file="environments/staging.tfvars"

# Destroy Prod
terraform destroy -var-file="environments/prod.tfvars"
```

### Dev Environment:

```bash
# Initialize with dev variables and backend config
terraform init -var-file="environments/dev.tfvars" -backend-config="key=sendr/dev/terraform.tfstate"

# Plan what will be created
terraform plan -var-file="environments/dev.tfvars"

# Apply the infrastructure
terraform apply -var-file="environments/dev.tfvars"
```

### Staging Environment:

```bash
# Initialize with staging variables and backend config
terraform init -var-file="environments/staging.tfvars" -backend-config="key=sendr/staging/terraform.tfstate"
terraform plan -var-file="environments/staging.tfvars"
terraform apply -var-file="environments/staging.tfvars"
```

### Prod Environment:

```bash
# Initialize with prod variables and backend config
terraform init -var-file="environments/prod.tfvars" -backend-config="key=sendr/prod/terraform.tfstate"
terraform plan -var-file="environments/prod.tfvars"
terraform apply -var-file="environments/prod.tfvars"
```

### What Terraform Creates:

| Resource | Name | Description |
|----------|------|-------------|
| VPC | `sendr-{env}-vpc` | Virtual Private Cloud |
| Database | `sendr-{env}-db` | PostgreSQL cluster (1-3 nodes) |
| Domain | `sendr.app` | DNS domain placeholder |
| CAA Record | `sendr.app` | Allows Let's Encrypt |
| Kubernetes | `sendr-{env}-cluster` | DOKS cluster |
| Project | `SendR-{env}` | DO project grouping |

### Post-Apply Outputs:

```bash
# Get all outputs
terraform output

# Get database connection string
terraform output database_connection_string

# Get Kubernetes cluster endpoint
terraform output kubernetes_cluster_endpoint

# Get kubeconfig (sensitive)
terraform output -raw kubernetes_kubeconfig > kubeconfig.yaml
```

---

## Step 3: Get kubeconfigs

After Kubernetes clusters are created:

```bash
# Install doctl if not already
brew install doctl  # macOS
# or: sudo apt install doctl  # Ubuntu

# Authenticate with DO
doctl auth init

# Save kubeconfig for each cluster
doctl kubernetes cluster kubeconfig save sendr-dev-cluster
doctl kubernetes cluster kubeconfig save sendr-staging-cluster
doctl kubernetes cluster kubeconfig save sendr-prod-cluster

# Verify
kubectl get nodes
```

### Convert to base64 for GitHub Secrets:

```bash
# Dev kubeconfig
cat ~/.kube/do-dev-cluster.yaml | base64 | tr -d '\n'
# Copy output and add as DEV_KUBECONFIG secret

# Staging kubeconfig
cat ~/.kube/do-staging-cluster.yaml | base64 | tr -d '\n'
# Copy output and add as STAGING_KUBECONFIG secret

# Prod kubeconfig
cat ~/.kube/do-prod-cluster.yaml | base64 | tr -d '\n'
# Copy output and add as PROD_KUBECONFIG secret
```

---

## Step 4: Purchase Domain

After Terraform creates the domain resource:

1. Go to DigitalOcean Console → Networking → Domains
2. You should see `sendr.app` listed (created by Terraform as placeholder)
3. Click on `sendr.app`
4. Click **"Purchase Domain"**
5. Complete the purchase (credit card/PayPal)
6. Domain is now active and managed by DigitalOcean

---

## Step 5: Configure GitHub Secrets for Workflows

Secrets are created **automatically by GitHub Actions** using `scripts/create-secrets.sh` during deployment. You need to configure these secrets in GitHub:

**Path:** Repository → Settings → Secrets and variables → Actions → New repository secret

### Per-Environment Secrets (DEV_, STAGING_, PROD_):

| Secret Name | Type | Description | Example |
|-------------|------|-------------|---------|
| `DEV_SENDR_DATABASE_URL` | Text | PostgreSQL dev connection string | `postgresql://user:pass@host:5432/sendr` |
| `STAGING_SENDR_DATABASE_URL` | Text | PostgreSQL staging connection string | `postgresql://user:pass@host:5432/sendr` |
| `PROD_SENDR_DATABASE_URL` | Text | PostgreSQL prod connection string | `postgresql://user:pass@host:5432/sendr` |
| `DEV_SENDR_SECRET_KEY` | Text | Flask dev secret key (min 32 chars) | `dev-super-tajny-klucz-min-32znaki!!` |
| `STAGING_SENDR_SECRET_KEY` | Text | Flask staging secret key (min 32 chars) | `staging-super-tajny-klucz-min-32znaki!!` |
| `PROD_SENDR_SECRET_KEY` | Text | Flask prod secret key (min 32 chars) | `prod-super-tajny-klucz-min-32znaki!!` |

### Common Secrets (shared across environments):

| Secret Name | Type | Description | Example |
|-------------|------|-------------|---------|
| `SENDR_SMTP_HOST` | Text | SMTP host | `smtp.resend.com` |
| `SENDR_SMTP_PORT` | Text | SMTP port | `587` |
| `SENDR_SMTP_USER` | Text | SMTP user | `resend` |
| `SENDR_SMTP_PASSWORD` | Text | SMTP password | `smtp_xxxxx` |
| `SENDR_RESEND_API_KEY` | Text | Resend API key | `re_xxxxx` |
| `GH_APP_ID` | Text | GitHub App ID | `123456` |
| `GH_APP_PRIVATE_KEY` | Text | GitHub App private key (base64) | `LS0tLS1...` |

### Variables (not Secrets):

| Variable Name | Type | Description |
|---------------|------|-------------|
| `SENDR_GITHUB_EMAIL` | Text | Email for docker-registry |

**How it works:**
1. Workflow builds and pushes images to GHCR
2. Workflow uses environment-specific secrets (DEV_*, STAGING_*, PROD_*)
3. Common secrets (SMTP, Resend) are shared across all environments
4. Workflow runs `scripts/create-secrets.sh` which creates K8s secrets
5. No manual secret creation needed after initial setup

---

## Step 6: Get kubeconfigs

After Kubernetes clusters are created:

```bash
# Install doctl if not already
brew install doctl  # macOS

# Authenticate with DO
doctl auth init

# Save kubeconfig for each cluster
doctl kubernetes cluster kubeconfig save sendr-dev-cluster
doctl kubernetes cluster kubeconfig save sendr-staging-cluster
doctl kubernetes cluster kubeconfig save sendr-prod-cluster
```

### Convert to base64 for GitHub Secrets:

```bash
# Dev kubeconfig
cat ~/.kube/do-dev-cluster.yaml | base64 | tr -d '\n'
# Copy output and add as DEV_KUBECONFIG secret

# Staging kubeconfig
cat ~/.kube/do-staging-cluster.yaml | base64 | tr -d '\n'
# Copy output and add as STAGING_KUBECONFIG secret

# Prod kubeconfig
cat ~/.kube/do-prod-cluster.yaml | base64 | tr -d '\n'
# Copy output and add as PROD_KUBECONFIG secret
```

---

## Step 7: Deploy to Kubernetes

```bash
# Set kubectl context for each cluster
kubectl config use-context do-sendr-dev-cluster

# Deploy Traefik (ingress controller with TLS)
kubectl apply -k k8s/base/traefik/ --server-side

# Wait for Traefik to be ready
kubectl rollout status deployment/traefik -n traefik

# Deploy application (backend, frontend)
kubectl apply -k k8s/overlays/dev --server-side

# Verify deployment
kubectl get pods -n sendr
kubectl get ingress -n sendr
```

### For Staging and Prod:

```bash
# Staging
kubectl config use-context do-sendr-staging-cluster
kubectl apply -k k8s/overlays/staging --server-side

# Prod
kubectl config use-context do-sendr-prod-cluster
kubectl apply -k k8s/overlays/prod --server-side
```

---

## Step 8: Get Load Balancer IP

After Traefik is deployed, check for Load Balancer IP:

```bash
# Get all services in traefik namespace
kubectl get svc -n traefik

# Expected output:
# NAME      TYPE           CLUSTER-IP      EXTERNAL-IP     PORT(S)
# traefik   LoadBalancer   10.245.x.x      203.0.113.5     80:31234/TCP,443:31235/TCP

# Extract external IP
kubectl get svc -n traefik traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
```

---

## Step 9: Configure DNS

After getting LB IPs, create DNS A records:

```bash
# Get the external IP
TRAEFIK_IP=$(kubectl get svc -n traefik traefik -o jsonpath='{.status.loadBalancer.ingress[0].ip}')

# Create A records for api and www
doctl compute domain records create sendr.app \
  --record-type A \
  --record-name api \
  --record-data $TRAEFIK_IP

doctl compute domain records create sendr.app \
  --record-type A \
  --record-name www \
  --record-data $TRAEFIK_IP

# Verify records
doctl compute domain records list sendr.app
```

### DNS Propagation:

- DNS changes may take up to 24-48 hours to propagate globally
- Let's Encrypt certificates will be automatically provisioned once DNS points to the LB

---

## GitHub Actions Triggers

| Trigger | Action | Permissions Needed |
|---------|--------|------------------|
| Push to `backend/` | Builds and pushes backend image to GHCR using GitHub App bot | packages:write |
| Push to `frontend/` | Builds and pushes frontend image to GHCR using GitHub App bot | packages:write |
| Push to `k8s/` | Deploys to all environments sequentially | KUBECONFIG secrets |
| Push to `terraform/` | Runs Terraform plan (PR) or apply (main) | DO_TOKEN, AWS credentials |

---

## Environment URLs

| Environment | Frontend URL | API URL |
|-------------|--------------|---------|
| Dev | https://dev.sendr.app | https://dev.api.sendr.app |
| Staging | https://staging.sendr.app | https://staging.api.sendr.app |
| Prod | https://sendr.app | https://api.sendr.app |

---

## Troubleshooting

### Pod not starting - ImagePullBackOff

```bash
# 1. Check if GHCR secret exists
kubectl get secret ghcr-secret -n sendr

# 2. Check if sendr-secrets exists
kubectl get secret sendr-secrets -n sendr

# 3. Describe the secret to see any errors
kubectl describe secret sendr-secrets -n sendr

# 4. Check pod events
kubectl describe pod -n sendr -l app=sendr-backend
kubectl describe pod -n sendr -l app=sendr-frontend

# 5. Check pod logs
kubectl logs -n sendr -l app=sendr-backend --tail=100
kubectl logs -n sendr -l app=sendr-frontend --tail=100
```

### Check pod logs

```bash
# Backend logs
kubectl logs -n sendr -l app=sendr-backend --tail=100

# Frontend logs
kubectl logs -n sendr -l app=sendr-frontend --tail=100

# Follow logs in real-time
kubectl logs -n sendr -l app=sendr-backend -f
```

### Check ingress/routing

```bash
# List ingresses
kubectl get ingress -n sendr

# Describe specific ingress
kubectl describe ingress sendr-backend -n sendr
```

### Update Secrets

```bash
# Delete and recreate secret with new values
kubectl delete secret sendr-secrets -n sendr
kubectl create secret generic sendr-secrets \
  --namespace=sendr \
  --from-literal=database-url="..." \
  ...

# Force pod restart to pick up new secrets
kubectl rollout restart deployment/sendr-backend -n sendr
kubectl rollout restart deployment/sendr-frontend -n sendr
```

---

## Cleanup

**Warning: This destroys all resources permanently!**

```bash
cd terraform
export AWS_PROFILE=digitalocean

# Destroy Dev
terraform workspace select dev
terraform destroy -var-file="environments/dev.tfvars"
# Type 'yes' when prompted

# Destroy Staging
terraform workspace select staging
terraform destroy -var-file="environments/staging.tfvars"

# Destroy Prod
terraform workspace select prod
terraform destroy -var-file="environments/prod.tfvars"
```

---

## File Structure

```
SendRR/
├── terraform/
│   ├── main.tf                          # Main Terraform config
│   ├── variables.tf                      # Input variables
│   ├── outputs.tf                       # Output values
│   ├── environments/
│   │   ├── dev.tfvars                   # Dev environment variables
│   │   ├── dev.tfvars.template         # Dev template (gitignore this)
│   │   ├── staging.tfvars               # Staging environment variables
│   │   ├── staging.tfvars.template      # Staging template
│   │   ├── prod.tfvars                  # Prod environment variables
│   │   └── prod.tfvars.template         # Prod template
│   └── modules/
│       ├── vpc/
│       ├── kubernetes/
│       ├── database/
│       └── domain/
├── k8s/
│   ├── base/
│   │   ├── namespace.yaml               # Namespaces (sendr, traefik)
│   │   ├── kustomization.yaml           # Base Kustomization
│   │   ├── backend/
│   │   │   ├── deployment.yaml          # Backend Deployment
│   │   │   ├── service.yaml             # Backend Service
│   │   │   └── ingress.yaml            # Backend Ingress (api.sendr.app)
│   │   ├── frontend/
│   │   │   ├── deployment.yaml          # Frontend Deployment
│   │   │   ├── service.yaml           # Frontend Service
│   │   │   └── ingress.yaml          # Frontend Ingress (sendr.app, www.sendr.app)
│   │   └── traefik/
│   │       ├── deployment.yaml         # Traefik Deployment (bez Helma!)
│   │       ├── service.yaml            # Traefik Service (LoadBalancer)
│   │       └── service-account.yaml   # Traefik ServiceAccount
│   └── overlays/
│       ├── dev/
│       │   ├── kustomization.yaml
│       │   ├── backend-image-tag.yaml   # Image: sendr-backend:dev-latest
│       │   └── frontend-image-tag.yaml # Image: sendr-frontend:dev-latest
│       ├── staging/
│       │   ├── kustomization.yaml
│       │   ├── backend-image-tag.yaml   # Image: sendr-backend:staging-latest
│       │   └── frontend-image-tag.yaml # Image: sendr-frontend:staging-latest
│       └── prod/
│           ├── kustomization.yaml
│           ├── backend-image-tag.yaml   # Image: sendr-backend:latest
│           └── frontend-image-tag.yaml # Image: sendr-frontend:latest
├── scripts/
│   └── create-secrets.sh               # Creates K8s secrets from GitHub Secrets
├── .github/
│   └── workflows/
│       ├── deploy-backend.yml           # Build & push backend to GHCR
│       ├── deploy-frontend.yml          # Build & push frontend to GHCR
│       ├── deploy-k8s.yml               # Deploy to Kubernetes
│       └── terraform.yml                # Terraform CI/CD
└── CLOUD_DEPLOYMENT_README.md           # This file
```

---

## GitHub App Authentication Flow

The `sendrr-ghcr-bot` GitHub App uses its own bot identity to authenticate with GHCR - **no user tokens needed**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GitHub Actions Runner                              │
│                                                                             │
│   Step 1: Generate JWT                                                       │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │  Uses: GH_APP_ID + GH_APP_PRIVATE_KEY                                 │ │
│   │  Creates: JWT token (expires in 10 minutes)                            │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│   Step 2: Exchange JWT for Installation Token                               │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │  POST https://api.github.com/app/installations/{id}/access_tokens     │ │
│   │  Returns: Bot's installation access token (not a user token!)        │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GitHub API                                       │
│                                                                             │
│   Step 3: Use installation token                                            │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │  Bot can now:                                                         │ │
│   │  - Read packages (pull images)                                        │ │
│   │  - Write packages (push images)                                       │ │
│   │  - Read repository contents                                          │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GHCR (GitHub Container Registry)                │
│                                                                             │
│   Step 4: Docker Login                                                      │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │  docker login ghcr.io -u x-access-token -p {installation_token}       │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│                                    ▼                                         │
│   Step 5: Push/Pull Images                                                 │
│   ┌──────────────────────────────────────────────────────────────────────┐ │
│   │  docker push ghcr.io/thephaseless/sendr/backend:latest                     │ │
│   │  docker pull ghcr.io/thephaseless/sendr/frontend:latest                    │ │
│   └──────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Security Notes

1. **GitHub App tokens** - Expire after 1 hour, manual refresh needed
2. **Secrets** - Stored in Kubernetes Secrets (manual management)
3. **No user tokens** - Used for GHCR, bot identity only
4. **Terraform state** - Stored in DO Spaces (encrypted)
5. **Kubeconfigs** - Stored as GitHub Secrets (at rest)
6. **Database password** - Auto-generated by DO, stored in Kubernetes Secret

---

## Support

For issues with:
- **Terraform** - Check DO Spaces backend connectivity
- **Kubernetes** - Check kubectl context and RBAC permissions
- **GHCR** - Verify GitHub App installation and repository access