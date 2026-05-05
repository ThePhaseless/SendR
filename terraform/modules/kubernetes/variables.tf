variable "cluster_name" {
  description = "Kubernetes cluster name"
  type        = string
}

variable "region" {
  description = "DigitalOcean region"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version"
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
  description = "VPC ID"
  type        = string
}

variable "tags" {
  description = "Tags to apply to cluster"
  type        = map(string)
}