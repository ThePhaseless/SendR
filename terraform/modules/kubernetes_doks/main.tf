data "digitalocean_kubernetes_versions" "current" {}

resource "digitalocean_kubernetes_cluster" "cluster" {
  name     = "sendr-k8s-${var.environment}"
  region   = var.region
  version  = var.kubernetes_version != "" ? var.kubernetes_version : data.digitalocean_kubernetes_versions.current.latest_version
  vpc_uuid = var.vpc_uuid

  node_pool {
    name       = "worker-pool"
    size       = "s-2vcpu-4gb"
    node_count = var.auto_scale ? null : var.node_count
    auto_scale = var.auto_scale
    min_nodes  = var.auto_scale ? var.min_nodes : null
    max_nodes  = var.auto_scale ? var.max_nodes : null
  }
}
