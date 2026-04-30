# Swarm Worker Helm Chart

## Установка

```bash
# Из локального чарта
helm install swarm-worker ./charts/swarm-worker \
  --set env.DEEPSEEK_API_KEY=sk-xxx

# С кастомными values
helm install swarm-worker ./charts/swarm-worker -f my-values.yaml
```

## Параметры

| Параметр | Описание | По умолчанию |
|----------|----------|-------------|
| `replicaCount` | Количество реплик | `1` |
| `image.repository` | Docker образ | `swarm-worker` |
| `env.DEEPSEEK_API_KEY` | API ключ DeepSeek | `""` |
| `env.GROQ_API_KEY` | API ключ Groq (fallback) | `""` |
| `autoscaling.enabled` | Включить HPA | `true` |
| `autoscaling.minReplicas` | Мин. реплик | `1` |
| `autoscaling.maxReplicas` | Макс. реплик | `10` |
| `resources.limits.cpu` | CPU limit | `2` |
| `resources.limits.memory` | Memory limit | `4Gi` |
| `persistence.enabled` | Persistent Volume | `true` |
| `persistence.size` | Размер кэша | `10Gi` |
| `prometheus.serviceMonitor.enabled` | ServiceMonitor | `true` |
