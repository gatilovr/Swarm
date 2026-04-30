# Swarm Scale

**Enterprise-система для масштабируемой обработки 1000+ файлов роем AI-агентов.**

Swarm Scale — это промышленная версия роя AI-агентов на базе [`swarm`](../swarm/),
предназначенная для параллельной обработки большого количества задач с кэшированием,
адаптивным rate limiting, выбором модели под сложность задачи и мониторингом.

---

## Архитектура

![](../plans/swarm-scale-architecture.md)

Подробное описание архитектуры см. в документе [`plans/swarm-scale-architecture.md`](../plans/swarm-scale-architecture.md).

### Ключевые компоненты

```
┌─────────────────────────────────────────────────────────┐
│                    Swarm Worker                           │
│  ┌─────────┐  ┌──────────┐  ┌──────────────┐           │
│  │  Cache   │  │  Rate    │  │    Model     │           │
│  │ Manager  │  │ Limiter  │  │  Selector    │           │
│  │ L1+L2+L3 │  │ Adaptive │  │  Complexity   │           │
│  └─────────┘  └──────────┘  └──────────────┘           │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │              Swarm (Architect → Coder → Reviewer) │   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Уровни кэша

| Уровень | Технология | Назначение |
|---------|-----------|------------|
| L1 | diskcache | Локальный кэш per-worker |
| L2 | Redis | Распределённый кэш между воркерами |
| L3 | S3/PostgreSQL | Долгосрочное хранение (заглушка) |

### Выбор модели

| Сложность | Архитектор | Кодер | Ревьюер |
|-----------|-----------|-------|---------|
| Critical | deepseek-reasoner | deepseek-chat | deepseek-reasoner |
| High | deepseek-reasoner | deepseek-chat | deepseek-chat |
| Medium | deepseek-chat | deepseek-chat | deepseek-chat |
| Low | deepseek-chat | deepseek-chat | None (skip) |

---

## Установка

### Через pip (в development режиме)

```bash
cd swarm-scale
pip install -e .
```

### С зависимостями для Kafka

```bash
pip install -e ".[kafka]"
```

### Для разработки

```bash
pip install -e ".[dev]"
```

### Docker

```bash
docker build -t swarm-scale .
docker run -e DEEPSEEK_API_KEY=your_key swarm-scale
```

---

## Быстрый старт

### Минимальный пример

```python
import asyncio
from swarm_scale import ScaleConfig, SwarmWorker, Task

async def main():
    config = ScaleConfig.from_env()
    worker = SwarmWorker(config)

    task = Task(
        task_id="task-1",
        content="Напиши функцию для сортировки массива на Python",
        repository="org/my-project",
        file_path="src/sort.py",
    )

    result = await worker.process_task(task)
    print(f"Plan: {result.plan}")
    print(f"Code: {result.code}")
    print(f"Approved: {result.approved}")

asyncio.run(main())
```

### Пакетная обработка

```python
import asyncio
from swarm_scale import ScaleConfig, SwarmWorker, Task

async def main():
    config = ScaleConfig(max_workers=5, batch_size=10)
    worker = SwarmWorker(config)

    tasks = [
        Task(
            task_id=f"task-{i}",
            content=f"Задача номер {i}",
            repository="org/repo",
            file_path=f"file{i}.py",
        )
        for i in range(10)
    ]

    results = await worker.process_batch(tasks)
    for r in results:
        print(f"{r.task_id}: {'OK' if r.approved else 'FAIL'} ({r.duration_sec}s)")

    print(f"Stats: {worker.stats}")

asyncio.run(main())
```

---

## Компоненты

### [`ScaleConfig`](src/swarm_scale/config.py)
Конфигурация всей системы, загружается из переменных окружения или создаётся программно.
Все параметры имеют префикс `SCALE_`:

| Переменная | По умолчанию | Описание |
|-----------|-------------|----------|
| `SCALE_CACHE_DIR` | `.swarm_cache` | Директория кэша |
| `SCALE_CACHE_SIZE_GB` | `10` | Максимальный размер кэша |
| `SCALE_CACHE_TTL_HOURS` | `24` | Время жизни кэша |
| `SCALE_REDIS_URL` | — | URL Redis |
| `SCALE_MAX_WORKERS` | `10` | Параллельных воркеров |
| `SCALE_BATCH_SIZE` | `20` | Размер батча |
| `SCALE_RPM_LIMIT` | `500` | Лимит запросов/мин |
| `SCALE_METRICS_PORT` | `8000` | Порт метрик |

### [`SwarmWorker`](src/swarm_scale/worker.py)
Основной воркер, объединяющий кэш, rate limiter, выбор модели и запуск роя.

### [`Task`](src/swarm_scale/task.py) / [`TaskResult`](src/swarm_scale/task.py)
Модели данных для задач и результатов с сериализацией в/из dict.

### [`CacheManager`](src/swarm_scale/cache.py)
Трёхуровневое кэширование: L1 (diskcache) → L2 (Redis) → L3 (заглушка).

### [`AdaptiveRateLimiter`](src/swarm_scale/rate_limiter.py)
Адаптивный rate limiter, снижающий RPM при 429 и восстанавливающий после успехов.

### [`ModelSelector`](src/swarm_scale/model_selector.py)
Выбирает модели для архитектора/кодера/ревьюера на основе ключевых слов задачи.

### [`ContextBuilder`](src/swarm_scale/context.py)
RAG-контекст: собирает релевантные файлы и ключевые слова для обогащения промпта.

### [`ProfileManager`](src/swarm_scale/profile.py)
Управление профилями проектов (язык, фреймворк, правила линтинга).

### [`InMemoryQueue`](src/swarm_scale/queue.py) / [`KafkaQueue`](src/swarm_scale/queue.py)
Абстракция очереди задач с in-memory реализацией для разработки и Kafka для production.

### [`metrics`](src/swarm_scale/metrics.py)
Prometheus метрики: счётчики задач, гистограммы длительности, токены, стоимость.

---

## Масштабирование

### Увеличение пропускной способности

1. **Увеличить `max_workers`** — до 50-100 на одной машине
2. **Добавить Redis** — включить распределённый кэш (`SCALE_REDIS_URL`)
3. **Горизонтальное масштабирование** — запустить несколько инстансов воркеров
4. **Kafka** — подключить очередь задач через Kafka
5. **Kubernetes HPA** — автоматическое масштабирование по CPU/memory

### Production-рекомендации

- Минимум 3 реплики для отказоустойчивости
- Redis Sentinel или Cluster для высокой доступности кэша
- Kafka с replication-factor >= 3
- Readiness probe через `/metrics` endpoint
- Resource limits: 2 CPU / 2GB RAM на pod

---

## Мониторинг

### Prometheus метрики

| Метрика | Тип | Описание |
|---------|-----|----------|
| `swarm_tasks_total` | Counter | Задачи по статусу |
| `swarm_task_duration_seconds` | Histogram | Длительность задач |
| `swarm_tokens_total` | Counter | Токены по модели |
| `swarm_cost_usd_total` | Counter | Стоимость |
| `swarm_active_workers` | Gauge | Активные воркеры |
| `swarm_queue_depth` | Gauge | Глубина очереди |
| `swarm_cache_size_bytes` | Gauge | Размер кэша |
| `swarm_rpm_current` | Gauge | Текущий RPM |

### Grafana

Импортируй дашборд из [`monitoring/grafana-dashboard.json`](monitoring/grafana-dashboard.json).

---

## Тестирование

```bash
cd swarm-scale
pip install -e ".[dev]"
python -m pytest tests/ -v
```

---

## Структура проекта

```
swarm-scale/
├── Dockerfile                    # Контейнеризация
├── README.md                     # Этот файл
├── pyproject.toml                # Конфигурация пакета
├── requirements.txt              # Зависимости
├── src/
│   └── swarm_scale/              # Исходный код
│       ├── __init__.py
│       ├── config.py             # ScaleConfig
│       ├── cache.py              # Многоуровневый кэш
│       ├── context.py            # RAG-контекст
│       ├── metrics.py            # Prometheus метрики
│       ├── model_selector.py     # Выбор модели
│       ├── profile.py            # Профили проектов
│       ├── queue.py              # Очередь задач
│       ├── rate_limiter.py       # Adaptive rate limiter
│       ├── task.py               # Модели задач
│       └── worker.py             # Основной воркер
├── tests/                        # Тесты
├── kubernetes/                   # Манифесты K8s
│   ├── deployment.yaml
│   ├── hpa.yaml
│   └── kustomization.yaml
├── monitoring/                   # Мониторинг
│   ├── prometheus.yml
│   └── grafana-dashboard.json
└── .github/workflows/            # CI/CD
    └── deploy.yml
```

---

## Лицензия

MIT
