variable "db_name" {
  description = "Database name"
  type        = string
}

variable "region" {
  description = "DigitalOcean region"
  type        = string
}

variable "engine_version" {
  description = "PostgreSQL engine version"
  type        = string
}

variable "node_size" {
  description = "Database node size"
  type        = string
}

variable "node_count" {
  description = "Number of database nodes"
  type        = number
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "tags" {
  description = "Tags to apply to database"
  type        = map(string)
}