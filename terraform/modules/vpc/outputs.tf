output "vpc_id" {
  description = "ID VPC"
  value       = data.digitalocean_vpc.sendrr.id
}

output "vpc_name" {
  description = "VPC name"
  value       = data.digitalocean_vpc.sendrr.name
}