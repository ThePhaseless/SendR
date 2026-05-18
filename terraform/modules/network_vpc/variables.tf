variable "environment" {
  description = "Physical deployment suffix used in DigitalOcean resource names"
  type        = string
}

variable "region" {
  description = "The region to deploy the VPC in"
  type        = string
}
