resource "digitalocean_spaces_bucket" "app_storage" {
  name   = "sendr-app-data-${var.environment}-${var.region}"
  region = var.region
  acl    = "private"

  lifecycle {
    prevent_destroy = false
  }
}

