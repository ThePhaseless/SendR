locals {
  resource_suffix = var.resource_suffix != "" ? var.resource_suffix : var.environment
}

module "network" {
  source      = "./modules/network_vpc"
  environment = local.resource_suffix
  region      = var.region
}

module "kubernetes" {
  source             = "./modules/kubernetes_doks"
  environment        = local.resource_suffix
  region             = var.region
  vpc_uuid           = module.network.vpc_id
  kubernetes_version = var.kubernetes_version
  node_count         = var.k8s_node_count
  auto_scale         = var.k8s_auto_scale
  min_nodes          = var.k8s_min_nodes
  max_nodes          = var.k8s_max_nodes
}

module "database" {
  source         = "./modules/database_postgres"
  environment    = local.resource_suffix
  region         = var.region
  vpc_uuid       = module.network.vpc_id
  k8s_cluster_id = module.kubernetes.cluster_id
}

module "storage" {
  source      = "./modules/storage_spaces"
  environment = local.resource_suffix
  region      = var.region
}

module "dns" {
  source      = "./modules/dns_domain"
  environment = var.environment
  domain_name = var.domain_name
  ingress_ip  = var.ingress_ip
}

