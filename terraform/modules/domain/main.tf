data "digitalocean_domain" "existing" {
  count = var.env == "dev" ? 0 : 1
  name  = var.domain_name
}

resource "digitalocean_domain" "main" {
  count = var.env == "dev" ? 1 : 0
  name  = var.domain_name
}

locals {
  domain_id = var.env == "dev" ? digitalocean_domain.main[0].id : data.digitalocean_domain.existing[0].id
}

resource "digitalocean_record" "caa" {
  count  = var.env == "dev" ? 1 : 0
  domain = local.domain_id
  type   = "CAA"
  name   = "@"
  value  = "letsencrypt.org."
  flags  = 0
  tag    = "issue"
}

resource "digitalocean_record" "api_a" {
  count  = var.target_ip != "" && var.env == "dev" ? 1 : 0
  domain = local.domain_id
  type   = "A"
  name   = "api"
  value  = var.target_ip
}

resource "digitalocean_record" "www_a" {
  count  = var.target_ip != "" && var.env == "dev" ? 1 : 0
  domain = local.domain_id
  type   = "A"
  name   = "www"
  value  = var.target_ip
}

resource "digitalocean_record" "dmarc" {
  count  = var.env == "dev" ? 1 : 0
  domain = local.domain_id
  type   = "TXT"
  name   = "_dmarc"
  value  = "v=DMARC1; p=none;"
  ttl    = 30
}

resource "digitalocean_record" "spf" {
  count  = var.env == "dev" ? 1 : 0
  domain = local.domain_id
  type   = "TXT"
  name   = "send"
  value  = "v=spf1 include:amazonses.com ~all"
  ttl    = 3600
}

resource "digitalocean_record" "mx_send" {
  count    = var.env == "dev" ? 1 : 0
  domain   = local.domain_id
  type     = "MX"
  name     = "send"
  value    = "feedback-smtp.eu-west-1.amazonses.com."
  priority = 10
  ttl      = 3600
}

resource "digitalocean_record" "dkim_resend" {
  count  = var.env == "dev" ? 1 : 0
  domain = local.domain_id
  type   = "TXT"
  name   = "resend._domainkey"
  value  = "p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDcO/bAWK/bfcL1A4CQiaKAuU77OU1NGH46vAkkelwSx1q5oE7GU/GNh8XvrGQhASFNuTCPMZKytD5NGEMgOvSHbBXnFrleq27WmPP0Wxq13QUOELmnXX6Mjv0NpEawPniLtjeQcne40GrvKRtIRoN5TyWrDMRreekIeOrlGCRE9wIDAQAB"
  ttl    = 3600
}