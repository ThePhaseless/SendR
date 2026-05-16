variable "domain_name" {
  description = "The root domain name purchased in DigitalOcean (e.g., sendr.com)"
  type        = string
}

variable "environment" {
  description = "The environment name (e.g., dev, staging, prod)"
  type        = string
}

variable "ingress_ip" {
  description = "The IP address of the Kubernetes Load Balancer (leave empty to configure later)"
  type        = string
  default     = ""
}
