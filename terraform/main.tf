module "network" {
  source      = "./modules/network_vpc"
  environment = var.environment
  region      = var.region
}

module "kubernetes" {
  source             = "./modules/kubernetes_doks"
  environment        = var.environment
  region             = var.region
  vpc_uuid           = module.network.vpc_id
  kubernetes_version = var.kubernetes_version
}

module "database" {
  source      = "./modules/database_postgres"
  environment = var.environment
  region      = var.region
  vpc_uuid    = module.network.vpc_id
}

module "storage" {
  source      = "./modules/storage_spaces"
  environment = var.environment
  region      = var.region
}

module "dns" {
  source      = "./modules/dns_domain"
  environment = var.environment
  domain_name = var.domain_name
  ingress_ip  = var.ingress_ip
}

resource "kubernetes_namespace" "sendr" {
  metadata {
    name = "sendr"
  }
  depends_on = [module.kubernetes]
}

resource "kubernetes_secret" "ghcr_secret" {
  metadata {
    name      = "ghcr-secret"
    namespace = kubernetes_namespace.sendr.metadata[0].name
  }

  type = "kubernetes.io/dockerconfigjson"

  data = {
    ".dockerconfigjson" = jsonencode({
      auths = {
        "ghcr.io" = {
          auth = base64encode("sendr-deploy-bot:${var.ghcr_token}")
        }
      }
    })
  }

  depends_on = [module.kubernetes]
}

