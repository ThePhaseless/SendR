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
  node_count         = var.k8s_node_count
  auto_scale         = var.k8s_auto_scale
  min_nodes          = var.k8s_min_nodes
  max_nodes          = var.k8s_max_nodes
}

module "database" {
  source         = "./modules/database_postgres"
  environment    = var.environment
  region         = var.region
  vpc_uuid       = module.network.vpc_id
  k8s_cluster_id = module.kubernetes.cluster_id
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

resource "kubernetes_secret" "sendr_secrets" {
  metadata {
    name      = "sendr-secrets"
    namespace = kubernetes_namespace.sendr.metadata[0].name
  }

  data = {
    "database-url"    = "postgresql+asyncpg://${module.database.database_user}:${module.database.database_password}@${module.database.database_host}:5432/${module.database.database_name}"
    "secret-key"      = var.app_secret_key
    "smtp-host"       = var.smtp_host
    "smtp-port"       = var.smtp_port
    "smtp-user"       = var.smtp_user
    "smtp-password"   = var.smtp_password
    "resend-api-key"  = var.resend_api_key
  }

  depends_on = [module.kubernetes, module.database]
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

