output "database_host" {
  value = digitalocean_database_cluster.postgres.private_host
}

output "database_user" {
  value = digitalocean_database_user.sendr_user.name
}

output "database_password" {
  value     = digitalocean_database_user.sendr_user.password
  sensitive = true
}

output "database_name" {
  value = digitalocean_database_db.sendr_db.name
}

output "database_port" {
  value = digitalocean_database_cluster.postgres.port
}
