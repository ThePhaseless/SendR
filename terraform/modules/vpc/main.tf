resource "digitalocean_vpc" "sendr" {
  name   = var.vpc_name
  region = var.region
  ip_range = var.vpc_cidr
}