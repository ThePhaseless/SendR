output "kubernetes_cluster_id" {
  value = module.kubernetes.cluster_id
}

output "kubernetes_cluster_name" {
  value = module.kubernetes.cluster_name
}

output "database_host" {
  value = module.database.database_host
}

output "database_url" {
  value     = "postgresql+psycopg://${module.database.database_user}:${module.database.database_password}@${module.database.database_host}:${module.database.database_port}/${module.database.database_name}?sslmode=require"
  sensitive = true
}

output "spaces_bucket_name" {
  value = module.storage.bucket_name
}

output "vpc_id" {
  value = module.network.vpc_id
}
