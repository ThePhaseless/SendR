output "cluster_endpoint" {
  description = "Kubernetes cluster endpoint"
  value       = data.digitalocean_kubernetes_cluster.sendrr.endpoint
}

output "database_connection_string" {
  description = "PostgreSQL connection string"
  value       = data.digitalocean_database_cluster.sendrr_db.connection_string
  sensitive   = true
}

output "database_host" {
  description = "Database host"
  value       = data.digitalocean_database_cluster.sendrr_db.host
}