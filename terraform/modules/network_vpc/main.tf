resource "digitalocean_vpc" "main" {
  name     = "sendr-vpc-${var.environment}"
  region   = var.region
  ip_range = "10.10.0.0/16"
}
