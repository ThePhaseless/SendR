variable "environment" {
  description = "Physical deployment suffix used in DigitalOcean resource names"
  type        = string
}

variable "region" {
  description = "The region to deploy the DOKS cluster in"
  type        = string
}

variable "vpc_uuid" {
  description = "The UUID of the VPC where the DOKS cluster will reside"
  type        = string
}

variable "kubernetes_version" {
  description = "Kubernetes version override (if empty, uses latest from DO API)"
  type        = string
  default     = ""
}

variable "node_count" {
  description = "Number of nodes (if auto_scale is false)"
  type        = number
  default     = 2
}

variable "auto_scale" {
  description = "Enable auto-scaling for the node pool"
  type        = bool
  default     = false
}

variable "min_nodes" {
  description = "Minimum number of nodes for auto-scaling"
  type        = number
  default     = 1
}

variable "max_nodes" {
  description = "Maximum number of nodes for auto-scaling"
  type        = number
  default     = 5
}
