data "digitalocean_kubernetes_versions" "current" {}

resource "digitalocean_kubernetes_cluster" "cluster" {
  name     = "sendr-k8s-${var.environment}"
  region   = var.region
  version  = var.kubernetes_version != "" ? var.kubernetes_version : data.digitalocean_kubernetes_versions.current.latest_version
  vpc_uuid = var.vpc_uuid

  node_pool {
    name       = "worker-pool"
    size       = "s-2vcpu-4gb"
    node_count = 2
  }
}
