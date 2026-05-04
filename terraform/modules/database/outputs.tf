output "connection_string" {
  description = "PostgreSQL connection string"
  value       = data.digitalocean_database_cluster.sendrr.connection_string
  sensitive   = true
}

output "host" {
  description = "Database host"
  value       = data.digitalocean_database_cluster.sendrr.host
}