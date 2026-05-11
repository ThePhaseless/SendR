output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "database_host" {
  description = "Database host"
  value       = module.database.host
}

output "database_connection_string" {
  description = "PostgreSQL connection string"
  value       = module.database.connection_string
  sensitive   = true
}

output "domain_name" {
  description = "Domain name"
  value       = module.domain.domain_name
}

output "kubernetes_cluster_id" {
  description = "Kubernetes cluster ID"
  value       = module.kubernetes.cluster_id
}

output "kubernetes_cluster_endpoint" {
  description = "Kubernetes cluster endpoint"
  value       = module.kubernetes.cluster_endpoint
}

output "kubernetes_cluster_urn" {
  description = "Kubernetes cluster URN"
  value       = module.kubernetes.cluster_urn
}

output "kubernetes_kubeconfig" {
  description = "Kubernetes kubeconfig"
  value       = module.kubernetes.kubeconfig
  sensitive   = true
}