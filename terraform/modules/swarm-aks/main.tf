terraform {
  required_version = ">= 1.5"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
  }
}

resource "azurerm_resource_group" "swarm" {
  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

resource "azurerm_kubernetes_cluster" "swarm" {
  name                = var.cluster_name
  location            = azurerm_resource_group.swarm.location
  resource_group_name = azurerm_resource_group.swarm.name
  dns_prefix          = var.cluster_name

  default_node_pool {
    name       = "workerpool"
    node_count = var.worker_node_count
    vm_size    = var.worker_vm_size
  }

  identity {
    type = "SystemAssigned"
  }

  tags = var.tags
}

resource "azurerm_container_registry" "swarm" {
  name                = var.acr_name
  resource_group_name = azurerm_resource_group.swarm.name
  location            = azurerm_resource_group.swarm.location
  sku                 = "Basic"
  admin_enabled       = false
  tags                = var.tags
}

resource "helm_release" "swarm_worker" {
  name       = "swarm-worker"
  repository = var.helm_chart_path != "" ? "" : "https://charts.swarm.dev"
  chart      = var.helm_chart_path != "" ? var.helm_chart_path : "swarm-worker"
  version    = var.helm_chart_version
  namespace  = var.namespace

  create_namespace = true

  values = [
    yamlencode({
      replicaCount = var.replica_count
      image = {
        repository = "${azurerm_container_registry.swarm.login_server}/swarm-worker"
        tag        = var.image_tag
      }
      env = var.extra_env_vars
      autoscaling = {
        enabled       = var.autoscaling_enabled
        minReplicas   = var.autoscaling_min_replicas
        maxReplicas   = var.autoscaling_max_replicas
      }
      resources = {
        limits = {
          cpu    = var.resource_limits_cpu
          memory = var.resource_limits_memory
        }
        requests = {
          cpu    = var.resource_requests_cpu
          memory = var.resource_requests_memory
        }
      }
      persistence = {
        enabled = var.persistence_enabled
        size    = var.persistence_size
      }
    })
  ]

  depends_on = [
    azurerm_kubernetes_cluster.swarm,
  ]
}

resource "kubernetes_namespace" "monitoring" {
  metadata {
    name = "monitoring"
  }
}

resource "helm_release" "prometheus" {
  count      = var.deploy_monitoring ? 1 : 0
  name       = "prometheus"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "prometheus"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name

  set {
    name  = "server.global.scrape_interval"
    value = "15s"
  }
}

resource "helm_release" "jaeger" {
  count      = var.deploy_monitoring ? 1 : 0
  name       = "jaeger"
  repository = "https://jaegertracing.github.io/helm-charts"
  chart      = "jaeger"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name

  set {
    name  = "collector.service.otlp.grpc.port"
    value = "4317"
  }
}
