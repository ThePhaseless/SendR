output "vpc_id" {
  description = "VPC ID"
  value       = digitalocean_vpc.sendr.id
}

output "vpc_name" {
  description = "VPC name"
  value       = digitalocean_vpc.sendr.name
}

output "vpc_urn" {
  description = "VPC URN"
  value       = digitalocean_vpc.sendr.urn
}