# Sprawdzamy czy domena została realnie zmieniona z domyślnej
locals {
  has_real_domain = var.domain_name != "sendr.com" && var.domain_name != ""
}

# Pobieramy informację o domenie, tylko jeśli zmieniono wartość z domyślnej
data "digitalocean_domain" "main" {
  count = local.has_real_domain ? 1 : 0
  name  = var.domain_name
}

# Tworzymy subdomenę dla środowiska (np. dev.twojadomena.com)
resource "digitalocean_record" "ingress" {
  count  = local.has_real_domain && var.ingress_ip != "" ? 1 : 0
  domain = data.digitalocean_domain.main[0].name
  type   = "A"

  name  = var.environment == "prod" ? "@" : var.environment
  value = var.ingress_ip
  ttl   = 300
}

# Zabezpieczenie dla prod (tworzymy też rekord www)
resource "digitalocean_record" "www_prod" {
  count  = local.has_real_domain && var.environment == "prod" && var.ingress_ip != "" ? 1 : 0
  domain = data.digitalocean_domain.main[0].name
  type   = "A"
  name   = "www"
  value  = var.ingress_ip
  ttl    = 300
}
