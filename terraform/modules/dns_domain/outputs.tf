output "domain_name" {
  value = data.digitalocean_domain.main.name
}

output "subdomain_fqdn" {
  value = length(digitalocean_record.ingress) > 0 ? digitalocean_record.ingress[0].fqdn : ""
}
