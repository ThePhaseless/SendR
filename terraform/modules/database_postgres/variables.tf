variable "environment" {
  description = "Physical deployment suffix used in DigitalOcean resource names"
  type        = string
}

variable "region" {
  description = "The region to deploy the database cluster in"
  type        = string
}

variable "vpc_uuid" {
  description = "The UUID of the VPC where the database will reside"
  type        = string
}

variable "k8s_cluster_id" {
  description = "The ID of the K8s cluster to allow in the database firewall"
  type        = string
}
