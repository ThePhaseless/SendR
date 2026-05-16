variable "do_token" {
  description = "DigitalOcean API Token"
  type        = string
  sensitive   = true
}

variable "environment" {
  description = "Environment name (e.g. dev, staging, prod)"
  type        = string
}

variable "region" {
  description = "DigitalOcean region"
  type        = string
  default     = "fra1"
}

variable "domain_name" {
  description = "Root domain name in DigitalOcean"
  type        = string
}

variable "spaces_access_key" {
  description = "Spaces Access Key"
  type        = string
  sensitive   = true
}

variable "spaces_secret_key" {
  description = "Spaces Secret Key"
  type        = string
  sensitive   = true
}

variable "ingress_ip" {
  description = "Public IP of the K8s Load Balancer (leave blank if not yet provisioned)"
  type        = string
  default     = ""
}

variable "kubernetes_version" {
  description = "Kubernetes version override (if empty, uses latest from DO API)"
  type        = string
  default     = ""
}
