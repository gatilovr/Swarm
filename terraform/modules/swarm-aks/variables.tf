variable "resource_group_name" {
  description = "Azure Resource Group name"
  type        = string
  default     = "swarm-rg"
}

variable "location" {
  description = "Azure region"
  type        = string
  default     = "westeurope"
}

variable "cluster_name" {
  description = "AKS cluster name"
  type        = string
  default     = "swarm-aks"
}

variable "acr_name" {
  description = "Azure Container Registry name (lowercase, unique)"
  type        = string
  default     = "swarmacr"
}

variable "worker_node_count" {
  description = "Number of worker nodes"
  type        = number
  default     = 3
}

variable "worker_vm_size" {
  description = "Worker node VM size"
  type        = string
  default     = "Standard_D4s_v3"
}

variable "namespace" {
  description = "Kubernetes namespace for Swarm"
  type        = string
  default     = "swarm"
}

variable "replica_count" {
  description = "Number of Swarm worker replicas"
  type        = number
  default     = 2
}

variable "image_tag" {
  description = "Docker image tag"
  type        = string
  default     = "latest"
}

variable "helm_chart_path" {
  description = "Path to local Helm chart (empty = use remote repo)"
  type        = string
  default     = "../../../charts/swarm-worker"
}

variable "helm_chart_version" {
  description = "Helm chart version"
  type        = string
  default     = "0.1.0"
}

variable "autoscaling_enabled" {
  description = "Enable HPA autoscaling"
  type        = bool
  default     = true
}

variable "autoscaling_min_replicas" {
  description = "Minimum replicas for HPA"
  type        = number
  default     = 1
}

variable "autoscaling_max_replicas" {
  description = "Maximum replicas for HPA"
  type        = number
  default     = 10
}

variable "resource_limits_cpu" {
  description = "CPU limit per pod"
  type        = string
  default     = "2"
}

variable "resource_limits_memory" {
  description = "Memory limit per pod"
  type        = string
  default     = "4Gi"
}

variable "resource_requests_cpu" {
  description = "CPU request per pod"
  type        = string
  default     = "500m"
}

variable "resource_requests_memory" {
  description = "Memory request per pod"
  type        = string
  default     = "1Gi"
}

variable "persistence_enabled" {
  description = "Enable persistent cache volume"
  type        = bool
  default     = true
}

variable "persistence_size" {
  description = "Cache volume size"
  type        = string
  default     = "10Gi"
}

variable "extra_env_vars" {
  description = "Additional environment variables"
  type        = map(string)
  default     = {}
}

variable "deploy_monitoring" {
  description = "Deploy Prometheus and Jaeger with Helm"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Azure resource tags"
  type        = map(string)
  default = {
    Environment = "production"
    Project     = "swarm"
    ManagedBy   = "terraform"
  }
}
