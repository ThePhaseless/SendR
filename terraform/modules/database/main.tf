resource "digitalocean_database_cluster" "sendr" {
  name       = var.db_name
  engine     = "pg"
  version    = var.engine_version
  region     = var.region
  size       = var.node_size
  node_count = var.node_count
  private_network_uuid = var.vpc_id

  tags = [for key, value in var.tags : "${key}:${value}"]
}