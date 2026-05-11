output "domain_name" {
  description = "The domain name"
  value       = var.env == "dev" ? digitalocean_domain.main[0].name : data.digitalocean_domain.existing[0].name
}

output "domain_urn" {
  description = "The URN of the domain"
  value       = var.env == "dev" ? digitalocean_domain.main[0].urn : data.digitalocean_domain.existing[0].urn
}