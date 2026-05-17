output "kubernetes_cluster_id" {
  value = module.kubernetes.cluster_id
}

output "database_host" {
  value = module.database.database_host
}

output "vpc_id" {
  value = module.network.vpc_id
}
