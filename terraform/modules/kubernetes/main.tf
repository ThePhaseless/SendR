data "digitalocean_kubernetes_versions" "current" {}

resource "digitalocean_kubernetes_cluster" "sendr" {
  name       = var.cluster_name
  region     = var.region
  version    = coalesce(var.kubernetes_version, data.digitalocean_kubernetes_versions.current.latest_version)
  vpc_uuid   = var.vpc_id

  node_pool {
    name       = "default"
    size       = var.node_size
    node_count = var.node_count
  }

  tags = [for key, value in var.tags : "${key}:${value}"]
}
