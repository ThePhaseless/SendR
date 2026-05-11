terraform {
  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }

  backend "s3" {
    endpoints = {
      s3 = "https://fra1.digitaloceanspaces.com"
    }
    key                         = "REPLACEME"  # Will be overridden by -backend-config
    bucket                      = "sendrr-terraform-state"
    region                      = "us-east-1"
    skip_requesting_account_id  = true
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    skip_region_validation      = true
    skip_s3_checksum            = true
  }
}

provider "digitalocean" {
  token = var.do_token
}

module "vpc" {
  source = "./modules/vpc"

  vpc_name = "${var.project_name}-${var.env}-vpc"
  vpc_cidr = var.vpc_cidr
  region   = var.region
  tags     = merge(var.tags, { environment = var.env })
}

module "database" {
  source = "./modules/database"

  db_name        = "${var.project_name}-${var.env}-db"
  region         = var.region
  engine_version = var.database_engine_version
  node_size      = var.database_node_size
  node_count     = var.database_node_count
  vpc_id         = module.vpc.vpc_id
  tags           = merge(var.tags, { environment = var.env })
}

module "kubernetes" {
  source = "./modules/kubernetes"

  cluster_name       = "${var.project_name}-${var.env}-cluster"
  region             = var.region
  kubernetes_version = var.kubernetes_version
  node_size          = var.kubernetes_node_size
  node_count         = var.kubernetes_node_count
  vpc_id             = module.vpc.vpc_id
  tags               = merge(var.tags, { environment = var.env })
}

module "domain" {
  source = "./modules/domain"

  domain_name = var.domain_name
  target_ip   = var.domain_target_ip
  env         = var.env
}

resource "digitalocean_project" "sendr_project" {
  name        = "SendR-${var.env}"
  description = "SendRR ${var.env} environment"
  purpose     = "Application"
  environment = var.env == "dev" ? "development" : (var.env == "staging" ? "staging" : "production")
}

resource "digitalocean_project_resources" "sendr_resources" {
  project = digitalocean_project.sendr_project.id
  resources = [
    module.kubernetes.cluster_urn,
    module.database.db_urn
  ]
}