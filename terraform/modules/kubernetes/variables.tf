variable "cluster_name" {
  description = "Cluster name"
  type        = string
}

variable "region" {
  description = "DigitalOcean region"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version (null = latest)"
  type        = string
  default     = null
}

variable "node_size" {
  description = "Node size"
  type        = string
}

variable "node_count" {
  description = "Number of nodes"
  type        = number
}

variable "vpc_id" {
  description = "VPC UUID"
  type        = string
}

variable "tags" {
  description = "Tags for resources"
  type        = map(string)
}