variable "vpc_name" {
  description = "VPC name"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
}

variable "region" {
  description = "DigitalOcean region"
  type        = string
}

variable "tags" {
  description = "Tags to apply to VPC"
  type        = map(string)
}