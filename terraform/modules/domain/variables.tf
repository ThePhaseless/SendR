variable "domain_name" {
  description = "Domain name"
  type        = string
}

variable "target_ip" {
  description = "IP for A records"
  type        = string
  default     = ""
}

variable "env" {
  description = "Environment name"
  type        = string
  default     = "dev"
}