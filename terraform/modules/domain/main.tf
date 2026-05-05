resource "digitalocean_domain" "main" {
  name = var.domain_name
}

resource "digitalocean_record" "dmarc" {
  domain = digitalocean_domain.main.id
  type   = "TXT"
  name   = "_dmarc"
  value  = "v=DMARC1; p=none;"
  ttl    = 30
}

resource "digitalocean_record" "spf" {
  domain = digitalocean_domain.main.id
  type   = "TXT"
  name   = "send"
  value  = "v=spf1 include:amazonses.com ~all"
  ttl    = 3600
}

resource "digitalocean_record" "mx_send" {
  domain   = digitalocean_domain.main.id
  type     = "MX"
  name     = "send"
  value    = "feedback-smtp.eu-west-1.amazonses.com."
  priority = 10
  ttl      = 3600
}

resource "digitalocean_record" "dkim_resend" {
  domain = digitalocean_domain.main.id
  type   = "TXT"
  name   = "resend._domainkey"
  value  = "p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDcO/bAWK/bfcL1A4CQiaKAuU77OU1NGH46vAkkelwSx1q5oE7GU/GNh8XvrGQhASFNuTCPMZKytD5NGEMgOvSHbBXnFrleq27WmPP0Wxq13QUOELmnXX6Mjv0NpEawPniLtjeQcne40GrvKRtIRoN5TyWrDMRreekIeOrlGCRE9wIDAQAB"
  ttl    = 3600
}
