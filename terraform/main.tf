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
    key                         = "sendr/terraform.tfstate"
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

  vpc_name = "${var.project_name}-vpc"
  vpc_cidr = var.vpc_cidr
  region   = var.region
  tags     = var.tags
}

module "kubernetes" {
  source = "./modules/kubernetes"

  cluster_name       = "${var.project_name}-cluster"
  region             = var.region
  kubernetes_version = var.kubernetes_version
  node_size          = var.kubernetes_node_size
  node_count         = var.kubernetes_node_count
  vpc_id             = module.vpc.vpc_id
  tags               = var.tags
}

module "database" {
  source = "./modules/database"

  db_name        = "${var.project_name}-db"
  region         = var.region
  engine_version = var.database_engine_version
  node_size      = var.database_node_size
  node_count     = var.database_node_count
  vpc_id         = module.vpc.vpc_id
  tags           = var.tags
}

module "domain" {
  source = "./modules/domain"

  domain_name = "sendrr.app"
}

data "digitalocean_project" "sendr_project" {
  name = "SendR"
}

resource "digitalocean_project_resources" "sendr_resources" {
  project = data.digitalocean_project.sendr_project.id
  resources = [
    module.kubernetes.cluster_urn,
    module.database.db_urn,
    module.domain.domain_urn
  ]
}