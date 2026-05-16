# We fetch available DO kubernetes versions
data "digitalocean_kubernetes_versions" "current" {
  version_prefix = "1.31."
}

locals {
  kubernetes_version = var.kubernetes_version != "" ? var.kubernetes_version : try(data.digitalocean_kubernetes_versions.current.latest_version, null)
}

resource "digitalocean_kubernetes_cluster" "cluster" {
  name     = "sendr-k8s-${var.environment}"
  region   = var.region

  version  = coalesce(local.kubernetes_version, "1.31.1-do.0")
  vpc_uuid = var.vpc_uuid

  node_pool {
    name       = "worker-pool"
    size       = "s-2vcpu-4gb"
    node_count = 2
  }
}
