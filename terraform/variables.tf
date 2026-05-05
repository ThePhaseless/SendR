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

variable "project_name" {
  description = "Project name used for resources"
  type        = string
  default     = "sendr"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "dev"
}

variable "region" {
  description = "DigitalOcean region"
  type        = string
  default     = "fra1"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "kubernetes_version" {
  description = "Kubernetes version"
  type        = string
  default     = null
}

variable "kubernetes_node_size" {
  description = "Kubernetes node size"
  type        = string
  default     = "s-2vcpu-2gb"
}

variable "kubernetes_node_count" {
  description = "Number of Kubernetes nodes"
  type        = number
  default     = 2
}

variable "database_node_size" {
  description = "Database node size"
  type        = string
  default     = "db-s-1vcpu-2gb"
}

variable "database_node_count" {
  description = "Number of database nodes"
  type        = number
  default     = 2
}

variable "database_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "16"
}

variable "tags" {
  description = "Tags to apply to all resources"
  type        = map(string)
  default = {
    env        = "dev"
    project    = "sendr"
    managed_by = "terraform"
  }
}