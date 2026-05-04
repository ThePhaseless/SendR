output "kubeconfig" {
  description = "Kubeconfig for cluster"
  value       = data.digitalocean_kubernetes_cluster_credentials.sendrr.kubeconfig
  sensitive   = true
}

output "cluster_id" {
  description = "cluster ID"
  value       = data.digitalocean_kubernetes_cluster.sendrr.id
}