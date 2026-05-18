# Live Deployment and CI/CD

SendR has one cloud deployment: `live`.

Pull requests and Terraform-only pushes still run static Terraform validation. Real DigitalOcean changes happen only through manual workflow dispatch or through the `SENDR_AUTO_DEPLOY_ENABLED=true` repository variable.

## Workflows

| Workflow | Purpose |
| --- | --- |
| `.github/workflows/terraform.yml` | Formats, initializes without backend, and validates Terraform. |
| `.github/workflows/docker-publish.yml` | Builds and publishes backend and frontend images to GHCR. |
| `.github/workflows/deploy-k8s.yml` | Applies live Terraform, writes Kubernetes secrets, deploys the live manifests, waits for Traefik, and updates DNS. |

## Trigger Behavior

| Trigger | Behavior |
| --- | --- |
| Pull request touching Terraform | Validation only. No cloud credentials or deploy. |
| Push to `main` | Validation and image publishing. Cloud deploy only when `SENDR_AUTO_DEPLOY_ENABLED=true`. |
| `workflow_dispatch` on deploy workflow | Manual live apply/deploy. Does not require `SENDR_AUTO_DEPLOY_ENABLED=true`. |

There are no separate staging or production deployment lanes. Release branches and tags do not map to separate cloud environments.

## GitHub Environment

The deployment jobs use the GitHub environment named `live`. Configure required reviewers there if manual approval should be required before live cloud changes.

## Compatibility Note

The live Terraform config reuses the original remote state key and physical DigitalOcean resource suffix from the earlier dev deployment. This avoids recreating the cluster, database, VPC, or Spaces bucket while presenting a single live deployment model in the repository.
