variable "do_token" {
  description = "DigitalOcean API Token"
  type        = string
  sensitive   = true
}

variable "environment" {
  description = "Logical deployment name. The live deployment uses this for DNS."
  type        = string
}

variable "resource_suffix" {
  description = "Existing physical resource suffix to preserve during deployment renames. Leave empty to use environment."
  type        = string
  default     = ""
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

variable "k8s_node_count" {
  description = "Number of nodes in the K8s cluster"
  type        = number
  default     = 2
}

variable "k8s_auto_scale" {
  description = "Enable auto-scaling for the K8s cluster"
  type        = bool
  default     = false
}

variable "k8s_min_nodes" {
  description = "Minimum nodes for auto-scaling"
  type        = number
  default     = 1
}

variable "k8s_max_nodes" {
  description = "Maximum nodes for auto-scaling"
  type        = number
  default     = 5
}
