resource "digitalocean_kubernetes_cluster" "cluster" {
  name     = "sendr-k8s-${var.environment}"
  region   = var.region

  # By-passing data source to avoid empty resolution during Apply.
  # We use the current stable version '1.32.2-do.0' supported by DO.
  version  = "1.32.2-do.0"
  vpc_uuid = var.vpc_uuid

  node_pool {
    name       = "worker-pool"
    size       = "s-2vcpu-4gb"
    node_count = 2
  }
}
