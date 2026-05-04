data "digitalocean_kubernetes_cluster" "sendrr" {
  name = var.cluster_name
}

data "digitalocean_kubernetes_cluster_credentials" "sendrr" {
  cluster_id = data.digitalocean_kubernetes_cluster.sendrr.id
}