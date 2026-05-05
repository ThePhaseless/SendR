output "domain_name" {
  description = "The domain name"
  value       = digitalocean_domain.main.name
}

output "domain_urn" {
  description = "The URN of the domain"
  value       = digitalocean_domain.main.urn
}
