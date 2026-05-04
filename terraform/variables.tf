variable "do_token" {
  description = "DigitalOcean API Token"
  type        = string
  sensitive   = true
}

variable "do_spaces_access_key" {
  description = "DigitalOcean Spaces Access Key"
  type        = string
  sensitive   = true
}

variable "do_spaces_secret_key" {
  description = "DigitalOcean Spaces Secret Key"
  type        = string
  sensitive   = true
}

variable "backend_secret_key" {
  description = "Secret key for backend - generate: openssl rand -base64 32"
  type        = string
  sensitive   = true
}

variable "github_app_credentials" {
  description = "GitHub App credentials"
  type = object({
    app_id           = string
    installation_id  = string
    private_key_base64 = string
  })
  sensitive = true
}
