variable "environment" {
  description = "The environment name (e.g. dev, staging, prod)"
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
