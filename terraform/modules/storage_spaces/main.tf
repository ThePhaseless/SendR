resource "digitalocean_spaces_bucket" "app_storage" {
  name   = "sendr-app-data-${var.environment}-${var.region}"
  region = var.region
  acl    = "private"

  # Blokada przed przypadkowym zniszczeniem (na dev ustawione na false, na prod warto dać true)
  lifecycle {
    prevent_destroy = false
  }
}

