# Pobieramy informację o domenie, którą kupiłeś i masz już na koncie DO
data "digitalocean_domain" "main" {
  name = var.domain_name
}

# Tworzymy subdomenę dla środowiska (np. dev.twojadomena.com)
# Rekord utworzy się TYLKO WTEDY, gdy podasz zmienną `ingress_ip`
resource "digitalocean_record" "ingress" {
  count  = var.ingress_ip != "" ? 1 : 0
  domain = data.digitalocean_domain.main.name
  type   = "A"

  # Dla prod chcemy czystą domenę (lub www), dla dev/staging przedrostek
  name  = var.environment == "prod" ? "@" : var.environment
  value = var.ingress_ip
  ttl   = 300
}

# Zabezpieczenie dla prod (tworzymy też rekord www)
resource "digitalocean_record" "www_prod" {
  count  = var.environment == "prod" && var.ingress_ip != "" ? 1 : 0
  domain = data.digitalocean_domain.main.name
  type   = "A"
  name   = "www"
  value  = var.ingress_ip
  ttl    = 300
}
