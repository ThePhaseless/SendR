resource "digitalocean_database_cluster" "postgres" {
  name                 = "sendr-db-${var.environment}"
  engine               = "pg"
  version              = "15"
  size                 = "db-s-1vcpu-1gb"
  region               = var.region
  node_count           = 1
  private_network_uuid = var.vpc_uuid
}

resource "digitalocean_database_db" "sendr_db" {
  cluster_id = digitalocean_database_cluster.postgres.id
  name       = "sendr"
}

# Firewall - zezwól klastrowi Kubernetes na dostęp do bazy
resource "digitalocean_database_firewall" "postgres-fw" {
  cluster_id = digitalocean_database_cluster.postgres.id

  rule {
    type  = "k8s"
    value = var.k8s_cluster_id
  }
}
