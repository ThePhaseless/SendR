output "cluster_endpoint" {
  description = "Kubernetes cluster endpoint"
  value       = module.kubernetes.cluster_endpoint
}

output "database_connection_string" {
  description = "PostgreSQL connection string"
  value       = module.database.connection_string
  sensitive   = true
}

output "database_host" {
  description = "Database host"
  value       = module.database.host
}

output "kubeconfig" {
  description = "Kubeconfig for cluster"
  value       = module.kubernetes.kubeconfig
  sensitive   = true
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "cluster_id" {
  description = "Kubernetes cluster ID"
  value       = module.kubernetes.cluster_id
}