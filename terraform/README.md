# SendR Infrastructure

This directory contains the Terraform configuration for the single live SendR deployment on DigitalOcean.

## Model

SendR now has one cloud deployment named `live`. Local development still uses local services and `SENDR_ENVIRONMENT=local`, but the repository no longer models separate dev, staging, and production cloud environments.

The live deployment currently reuses the original DigitalOcean resources that were first created for the earlier dev deployment. To avoid replacing the existing DOKS cluster, PostgreSQL database, VPC, and Spaces bucket, [terraform/environments/live/terraform.tfvars.example](environments/live/terraform.tfvars.example) sets:

- `environment = "live"` for the logical deployment and DNS label.
- `resource_suffix = "dev"` for existing physical resource names.

Do not remove `resource_suffix = "dev"` unless you intentionally plan and execute a resource rename or migration.

## Modules

- `network_vpc` creates the private DigitalOcean VPC.
- `kubernetes_doks` creates the DOKS cluster.
- `database_postgres` creates PostgreSQL and allows the cluster as a trusted source.
- `storage_spaces` creates the Spaces bucket for uploaded files.
- `dns_domain` points live DNS records at the Traefik load balancer.

## Validation

Run static validation without cloud credentials:

```bash
cd terraform
mise x terraform@latest -- terraform fmt -check -recursive
mise x terraform@latest -- terraform init -backend=false -no-color
mise x terraform@latest -- terraform validate -no-color
```

Run an authenticated plan only with the live backend and reviewed credentials. Include the current Traefik IP when DNS records already exist:

```bash
cd terraform
mise x terraform@latest -- terraform init -backend-config="environments/live/backend.conf" -reconfigure -no-color
mise x terraform@latest -- terraform plan -no-color -var-file="environments/live/terraform.tfvars.example" -var="ingress_ip=$TRAEFIK_IP"
```

A safe live plan must not replace the DOKS cluster, PostgreSQL database, VPC, or Spaces bucket. DNS changes should only rename or point live records.
