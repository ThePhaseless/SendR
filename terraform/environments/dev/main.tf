terraform {
  backend "s3" {
    endpoint                  = "https://fra1.digitaloceanspaces.com"
    region                   = "us-east-1"
    bucket                   = "sendrr-terraform-state"
    key                      = "dev/terraform.tfstate"
    access_key               = var.do_spaces_access_key
    secret_key               = var.do_spaces_secret_key
    skip_credentials_validation = true
    skip_metadata_api_check     = true
    force_path_style             = true
  }
}

provider "digitalocean" {
  token = var.do_token
}

data "digitalocean_kubernetes_cluster" "sendrr" {
  name = "sendrr-cluster"
}

data "digitalocean_database_cluster" "sendrr_db" {
  name = "sendrr-db"
}

module "vpc" {
  source   = "../../modules/vpc"
  vpc_name = "sendrr-vpc"
}

module "kubernetes" {
  source       = "../../modules/kubernetes"
  cluster_name = "sendrr-cluster"
}

module "database" {
  source  = "../../modules/database"
  db_name = "sendrr-db"
}