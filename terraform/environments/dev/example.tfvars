# Create terraform.tfvars with secrets

do_token = "your-do-token"
backend_secret_key = "openssl rand -base64 32"
do_spaces_access_key = "your-spaces-key"
do_spaces_secret_key = "your-spaces-secret"

github_app_credentials = {
  app_id = "your-app-id"
  installation_id = "your-installation-id"
  private_key_base64 = "your-base64-private-key"
}