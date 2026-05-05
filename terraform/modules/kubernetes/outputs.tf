output "kubeconfig" {
  description = "Kubeconfig for cluster"
  value       = digitalocean_kubernetes_cluster.sendr.kube_config[0].raw_config
  sensitive   = true
}

output "cluster_id" {
  description = "Cluster ID"
  value       = digitalocean_kubernetes_cluster.sendr.id
}

output "cluster_endpoint" {
  description = "Cluster endpoint"
  value       = digitalocean_kubernetes_cluster.sendr.endpoint
}

output "cluster_ca_certificate" {
  description = "Cluster CA certificate"
  value       = digitalocean_kubernetes_cluster.sendr.kube_config[0].cluster_ca_certificate
}

output "cluster_urn" {
  description = "Cluster URN"
  value       = digitalocean_kubernetes_cluster.sendr.urn
}