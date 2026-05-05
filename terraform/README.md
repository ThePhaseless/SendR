# Terraform & DigitalOcean Spaces (S3 Backend) Authentication

To securely store the Terraform state in DigitalOcean Spaces, this project uses the S3-compatible backend. Because we don't hardcode credentials in the configuration, you need to authenticate using the **AWS CLI**.

Follow these steps before running any Terraform commands:

## 1. Configure the AWS CLI Profile

Open your terminal and run the following command to create a dedicated profile named `digitalocean`:

```bash
aws configure --profile digitalocean
```

When prompted, provide your **DigitalOcean Spaces keys**:
*   **AWS Access Key ID**: _[Paste your DO Spaces Access Key]_
*   **AWS Secret Access Key**: _[Paste your DO Spaces Secret Key]_
*   **Default region name**: `us-east-1`
*   **Default output format**: `json`

## 2. Export the Profile as an Environment Variable

Before running `terraform init` or `terraform apply`, you must tell Terraform to use the newly created profile. 

Set the `AWS_PROFILE` environment variable in your terminal session:

### For Git Bash, WSL, Linux, or macOS:
```bash
export AWS_PROFILE=digitalocean
```

### For PowerShell (Windows):
```powershell
$env:AWS_PROFILE="digitalocean"
```

### For Command Prompt (CMD Windows):
```cmd
set AWS_PROFILE=digitalocean
```

## 3. Run Terraform

Once the profile is set in your current terminal session, you can run Terraform commands normally:

```bash
terraform init
terraform apply
```

_Note: Remember that to authenticate the DigitalOcean provider itself (to create droplets, databases, etc.), you still need the `do_token` (Personal Access Token), typically provided in your `terraform.tfvars` file._