output "domain_name" {
  value = length(data.digitalocean_domain.main) > 0 ? data.digitalocean_domain.main[0].name : ""
}

output "subdomain_fqdn" {
  value = length(digitalocean_record.ingress) > 0 ? digitalocean_record.ingress[0].fqdn : ""
}
