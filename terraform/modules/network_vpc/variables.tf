variable "environment" {
  description = "The environment name (e.g. dev, staging, prod)"
  type        = string
}

variable "region" {
  description = "The region to deploy the VPC in"
  type        = string
}
