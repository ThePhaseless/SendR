# We fetch available DO kubernetes versions
data "digitalocean_kubernetes_versions" "current" {
  version_prefix = "1.31."
}

resource "digitalocean_kubernetes_cluster" "cluster" {
  name     = "sendr-k8s-${var.environment}"
  region   = var.region
  
  # DO API latest_version can sometimes return null in CI/CD. 
  # We use the first valid version from the array, or a hard fallback.
  version  = try(
    data.digitalocean_kubernetes_versions.current.valid_versions[0],
    "1.31.1-do.5"
  )
  vpc_uuid = var.vpc_uuid

  node_pool {
    name       = "worker-pool"
    size       = "s-2vcpu-4gb"
    node_count = 2
  }
}
