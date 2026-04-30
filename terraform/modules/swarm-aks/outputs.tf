output "cluster_id" {
  description = "AKS cluster ID"
  value       = azurerm_kubernetes_cluster.swarm.id
}

output "cluster_fqdn" {
  description = "AKS cluster FQDN"
  value       = azurerm_kubernetes_cluster.swarm.fqdn
}

output "acr_login_server" {
  description = "ACR login server"
  value       = azurerm_container_registry.swarm.login_server
}

output "helm_release_name" {
  description = "Helm release name"
  value       = helm_release.swarm_worker.name
}

output "kube_config" {
  description = "Kubernetes config (sensitive)"
  value       = azurerm_kubernetes_cluster.swarm.kube_config_raw
  sensitive   = true
}
