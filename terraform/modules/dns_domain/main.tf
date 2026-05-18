locals {
  has_real_domain = var.domain_name != "sendr.com" && var.domain_name != ""
}

data "digitalocean_domain" "main" {
  count = local.has_real_domain ? 1 : 0
  name  = var.domain_name
}

resource "digitalocean_record" "ingress" {
  count  = local.has_real_domain && var.ingress_ip != "" ? 1 : 0
  domain = data.digitalocean_domain.main[0].name
  type   = "A"

  name  = var.environment
  value = var.ingress_ip
  ttl   = 300
}

resource "digitalocean_record" "subdomains" {
  count  = local.has_real_domain && var.ingress_ip != "" ? 1 : 0
  domain = data.digitalocean_domain.main[0].name
  type   = "A"

  name  = "*.${var.environment}"
  value = var.ingress_ip
  ttl   = 300
}
