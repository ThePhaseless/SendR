resource "digitalocean_kubernetes_cluster" "cluster" {
  name     = "sendr-k8s-${var.environment}"
  region   = var.region
  # Set a static stable version compatible with DO, avoiding data source failures during apply
  version  = "1.31.1-do.5"
  vpc_uuid = var.vpc_uuid

  node_pool {
    name       = "worker-pool"
    size       = "s-2vcpu-4gb"
    node_count = 2
  }
}
