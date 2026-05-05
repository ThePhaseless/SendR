output "connection_string" {
  description = "PostgreSQL connection string"
  value       = digitalocean_database_cluster.sendr.uri
  sensitive   = true
}

output "host" {
  description = "Database host"
  value       = digitalocean_database_cluster.sendr.host
}

output "db_urn" {
  description = "Database URN"
  value       = digitalocean_database_cluster.sendr.urn
}