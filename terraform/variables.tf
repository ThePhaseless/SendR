variable "do_token" {
  description = "DigitalOcean API Token"
  type        = string
  sensitive   = true
}

variable "env" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "project_name" {
  description = "Project name used for resources"
  type        = string
  default     = "sendr"
}

variable "region" {
  description = "DigitalOcean region"
  type        = string
  default     = "fra1"
}

variable "domain_name" {
  description = "Domain name to register"
  type        = string
  default     = "sendr.app"
}

variable "domain_target_ip" {
  description = "IP for domain A records (empty = no record creation)"
  type        = string
  default     = ""
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "database_engine_version" {
  description = "PostgreSQL engine version"
  type        = string
  default     = "16"
}

variable "database_node_size" {
  description = "Database node size"
  type        = string
  default     = "db-s-1vcpu-2gb"
}

variable "database_node_count" {
  description = "Number of database nodes"
  type        = number
  default     = 1
}

variable "tags" {
  description = "Tags for resources"
  type        = map(string)
  default = {
    project    = "sendr"
    managed_by = "terraform"
  }
}

variable "kubernetes_version" {
  description = "Kubernetes version (null = latest)"
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