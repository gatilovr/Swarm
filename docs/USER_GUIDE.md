# Swarm: Руководство пользователя

## 1. Что такое Swarm?

**Swarm** — это многоагентная AI-система, которая автоматически пишет код по вашему техническому заданию. Внутри неё работают три AI-агента (Архитектор → Кодер → Ревьюер), которые взаимодействуют в цикле, пока не получат качественный результат.

### Ключевые возможности

- **Три AI-агента**: Архитектор анализирует задачу и составляет план, Кодер пишет код, Ревьюер проверяет качество
- **Автоматический выбор модели**: система сама определяет сложность задачи (low/medium/high/critical) и выбирает подходящую LLM-модель
- **LLM-провайдер с fallback**: основная модель — DeepSeek, при ошибках автоматически переключается на Groq или OpenAI
- **Многоуровневый кэш**: L1 (локальный дисковый кэш) + L2 (Redis) — повторные задачи выполняются мгновенно
- **Сжатие промптов**: длинные контексты автоматически сжимаются через LLMLingua для экономии токенов
- **Наблюдаемость**: Prometheus метрики, Grafana дашборды, OpenTelemetry трассировка, Jaeger
- **Kubernetes**: готовый Helm chart и Terraform модуль для Azure AKS

### Архитектура проекта (кратко)

```
swarm/           — ядро: AI-агенты и граф на LangGraph
swarm-mcp/       — MCP-сервер для интеграции с Roo Code
swarm-scale/     — масштабирование: кэш, rate limiter, воркер, метрики
charts/          — Helm chart для Kubernetes
terraform/       — Terraform для Azure AKS
```

---

## 2. Быстрый старт (5 шагов)

### 2.1. Установка

Клонируйте репозиторий и установите зависимости:

```bash
git clone https://github.com/your-org/swarm.git
cd swarm

# Установка базового пакета
pip install -e swarm/

# Установка MCP-сервера
pip install -e swarm-mcp/

# (Опционально) Установка масштабируемой версии
pip install -e swarm-scale/
```

### 2.2. Конфигурация (`.env`)

Скопируйте пример конфигурации и укажите свой API-ключ DeepSeek:

```bash
cp .env.example .env
```

Откройте [`.env`](.env) и заполните обязательные поля:

```ini
DEEPSEEK_API_KEY=ваш_ключ_deepseek

# Опционально: включить Worker с кэшем
MCP_USE_WORKER=true
```

Другие переменные можно пока оставить по умолчанию — система запустится и без них.

### 2.3. Запуск

Swarm можно запустить тремя способами:

**Способ 1 — Через Roo Code (рекомендуется):**  
Подключите MCP-сервер (см. раздел 3) и вызывайте инструмент `run_swarm` прямо из Roo Code.

**Способ 2 — Через CLI:**  
Выполните одну задачу из терминала:

```bash
python -m swarm_scale task "Напиши функцию сортировки на Python"
```

**Способ 3 — Как Python-библиотека:**

```python
import asyncio
from swarm import SwarmRunner, SwarmConfig

async def main():
    config = SwarmConfig.from_env()
    runner = SwarmRunner(config)
    result = await runner.run("Напиши калькулятор на Python")
    print(result["code"])

asyncio.run(main())
```

### 2.4. Первый запуск

При первом запуске Swarm:

1. **Архитектор** анализирует ваше ТЗ и создаёт план
2. **Кодер** пишет код по плану
3. **Ревьюер** проверяет код на ошибки
4. Если код не прошёл проверку, он отправляется на доработку (до 3 циклов)
5. Готовый результат возвращается вам

```
============================================================
  [AI] РОЙ AI-АГЕНТОВ
  Архитектор -> Кодер -> Ревьюер (с циклом доработки)
============================================================

  Введите задачу для роя AI-агентов:
  > Напиши калькулятор на Python
```

### 2.5. Что дальше?

- Настройте [`MCP_USE_WORKER=true`](.env.example:4) — включит кэш (повторные задачи будут мгновенными) и автоматический выбор модели
- Подключите Redis через [`REDIS_URL`](.env.example) для распределённого кэша между запусками
- Настройте OpenTelemetry для отправки трейсов в Jaeger или SigNoz

---

## 3. Подключение к Roo Code через MCP

### 3.1. Настройка MCP-сервера

Swarm предоставляет MCP-сервер (v2.0), который регистрирует **5 инструментов** в Roo Code. После настройки вы сможете не только запускать Swarm, но и спрашивать о проекте, проверять статус, читать файлы и безопасно выполнять команды.

### 3.2. Конфиг `.roo/mcp.json`

Добавьте в файл [`.roo/mcp.json`](.roo/mcp.json) следующий блок:

```json
{
  "mcpServers": {
    "swarm": {
      "command": "python",
      "args": ["-m", "swarm_mcp"],
      "env": {
        "DEEPSEEK_API_KEY": "ваш_ключ",
        "MCP_ORCHESTRATION": "true"
      },
      "disabled": false,
      "alwaysAllow": [
        "run_swarm",
        "swarm_status",
        "swarm_ask",
        "swarm_files"
      ]
    }
  }
}
```

**Важно**: Путь `python` должен быть доступен в `PATH`. Если вы используете виртуальное окружение, укажите полный путь к интерпретатору:

```json
"command": "C:/Users/.../venv/Scripts/python.exe"
```

**Примечание**: `swarm_execute` не добавлен в `alwaysAllow` — он требует явного одобрения пользователя каждый раз.

### 3.3. Инструменты MCP

Сервер предоставляет 5 продуктовых инструментов. В отличие от микросервисной архитектуры (35+ инструментов), v2.0 использует подход **«продукт, а не инфраструктура»** — Roo Code даёт задачу, Swarm сам определяет, как её выполнить наилучшим образом.

---

#### `run_swarm`

Запускает полный цикл разработки: Архитектор → Кодер → Ревьюер.

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|-------------|-------------|----------|
| `task` | `string` | ✅ | — | Детальное техническое задание |
| `context` | `string` | ❌ | `""` | Дополнительный контекст (файлы, архитектура, ограничения) |
| `mode` | `enum` | ❌ | `full` | `full` — полный цикл, `plan` — только план без записи файлов |
| `complexity` | `enum` | ❌ | `auto` | Подсказка сложности: `auto`, `low`, `medium`, `high`, `critical` |
| `project_files` | `int` | ❌ | `0` | Примерное количество файлов в проекте |

**Возвращает JSON** с полями: `status`, `summary`, `plan`, `code`, `review`, `iterations`, `files`, `cached`, `tokens`.

---

#### `swarm_status`

Показывает состояние проекта без запуска полного анализа.

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|-------------|-------------|----------|
| `scope` | `enum` | ❌ | `summary` | `summary` — кратко, `full` — детально |

**Что показывает:**
- Количество файлов и строк кода
- Расширения и языки
- Git-статус (ветка, чист/грязный, ahead/behind)
- Наличие тестовых файлов
- Конфигурационные файлы

---

#### `swarm_ask`

Задаёт вопрос о проекте и получает структурированный ответ.

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|-------------|-------------|----------|
| `question` | `string` | ✅ | — | Вопрос на естественном языке |
| `files` | `string[]` | ❌ | — | Ограничить анализ конкретными файлами |

**Поддерживаемые категории:**
- Архитектура: «какая архитектура?», «как устроен проект?»
- Зависимости: «какие библиотеки используются?»
- Безопасность: «есть ли уязвимости?», «как с аутентификацией?»
- Производительность: «где узкое место?»
- Тесты: «какие есть тесты?», «какое покрытие?»
- Качество кода: «как улучшить код?»
- Документация: «есть ли документация?»
- Конфигурация: «какие настройки?»
- Общие: «что это за проект?»

---

#### `swarm_execute`

Безопасно выполняет команду терминала с 4-уровневой проверкой безопасности.

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|-------------|-------------|----------|
| `command` | `string` | ✅ | — | Команда для выполнения |
| `timeout` | `int` | ❌ | `60` | Таймаут в секундах (макс. 300) |
| `approved` | `bool` | ❌ | `false` | Предварительное одобрение |

**4 уровня защиты:**
1. **System Prompt** — промпт Roo Code ограничивает опасные действия
2. **`.swarm-policy.toml`** — файл политик с 3 уровнями (`auto_allow` / `require_approval` / `deny`)
3. **CommandSanitizer** — кодовая проверка команд (case-insensitive, частичное совпадение)
4. **Roo Code approval** — пользователь явно подтверждает выполнение

**Политики по умолчанию:** `pip install` и `pytest` — auto_allow; `git push` и `sudo` — require_approval; `rm -rf /` и `format C:` — deny.

---

#### `swarm_files`

Читает содержимое файлов проекта по glob-паттерну.

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|-------------|-------------|----------|
| `pattern` | `string` | ✅ | — | Glob-паттерн (например, `**/*.py`) |
| `max_lines` | `int` | ❌ | `100` | Максимум строк на файл |

---

### 3.4. Примеры вызовов из Roo Code

```
Задача: "Реализуй систему аутентификации с JWT, refresh токенами и ролями пользователей"
```

Что произойдёт:
1. Система обнаружит `auth`, `security` → сложность `critical`
2. Будет использована модель `deepseek-reasoner` для архитектора и ревьюера
3. Каждый этап пройдёт тщательную проверку
4. Результат: production-ready код аутентификации

---

## 4. CLI: `python -m swarm_scale`

CLI-интерфейс позволяет запускать задачи из командной строки без Roo Code. Доступны три режима: одиночная задача, пакетная обработка и режим worker-демона.

### 4.1. Одиночная задача

```bash
python -m swarm_scale task "Напиши тест для функции сортировки"
```

Опции:
- `--repo org/repo` — указать репозиторий (для кэша)
- `--file path/to/file.py` — путь к файлу
- `--json` — вывод в JSON
- `-v` — подробный лог (DEBUG)
- `-c .env` — путь к файлу конфигурации

Пример с JSON-выводом:

```bash
python -m swarm_scale task "Рефакторинг модуля auth" --json
```

### 4.2. Пакетная обработка (batch)

Создайте JSON-файл с задачами, например [`tasks.json`](examples/quicksort.py):

```json
[
  {
    "task_id": "task-001",
    "content": "Напиши функцию быстрой сортировки"
  },
  {
    "task_id": "task-002",
    "content": "Напиши функцию бинарного поиска"
  }
]
```

Запустите пакет:

```bash
python -m swarm_scale batch tasks.json
```

Результаты сохранятся в `tasks_results.json`. Сводка покажет:

```
============================================================
  Батч завершён
============================================================
  ✅ Успешно:  2
  ⚡ Из кэша:  0
  ❌ Ошибок:   0
  Всего:      2
  Результаты: tasks_results.json
```

### 4.3. Режим worker (daemon)

Воркер запускается как демон и обрабатывает задачи из очереди:

```bash
# InMemory-очередь (по умолчанию)
python -m swarm_scale worker --queue memory

# Kafka-очередь (требуется SCALE_KAFKA_SERVERS)
python -m swarm_scale worker --queue kafka
```

Воркер поддерживает graceful shutdown по `Ctrl+C` и выводит статистику:

```
🚀 Воркер запущен (очередь: memory, макс. воркеров: 10)
  Ожидание задач... (Ctrl+C для выхода)

📥 Получена задача: task-001 | Напиши функцию сортировки...
  ✅ task-001 | ⏱ 12.34с
  📊 processed=1, cached=0, errors=0
```

---

## 5. Docker

### 5.1. Сборка образа

Соберите Docker-образ для MCP-сервера или масштабируемого воркера:

```bash
# MCP-сервер
cd swarm-mcp
docker build -t swarm-mcp .

# Swarm Worker
cd swarm-scale
docker build -t swarm-worker .
```

### 5.2. Запуск контейнера

```bash
docker run -d \
  --name swarm-worker \
  -e DEEPSEEK_API_KEY=ваш_ключ \
  -e MCP_USE_WORKER=true \
  -p 8000:8000 \
  swarm-worker
```

Для MCP-сервера (работает через stdio, обычно не требуется публикация портов):

```bash
docker run -it \
  --name swarm-mcp \
  -e DEEPSEEK_API_KEY=ваш_ключ \
  swarm-mcp
```

### 5.3. Docker Compose

Пример `docker-compose.yml` для полноценного развёртывания:

```yaml
version: '3.8'
services:
  swarm-worker:
    build: ./swarm-scale
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - MCP_USE_WORKER=true
      - REDIS_URL=redis://redis:6379
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317
    ports:
      - "8000:8000"
    depends_on:
      - redis
      - jaeger

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  jaeger:
    image: jaegertracing/all-in-one:latest
    ports:
      - "16686:16686"  # UI
      - "4317:4317"    # gRPC OTLP
```

---

## 6. Kubernetes

### 6.1. Установка через Helm

Swarm поставляется с готовым Helm chart в директории [`charts/swarm-worker/`](charts/swarm-worker/).

Установите в кластер:

```bash
helm upgrade --install swarm-worker ./charts/swarm-worker \
  --set env.DEEPSEEK_API_KEY=ваш_ключ \
  --set env.REDIS_URL=redis://redis-service:6379 \
  --namespace swarm --create-namespace
```

Параметры Helm chart (из [`values.yaml`](charts/swarm-worker/values.yaml)):

| Параметр | По умолчанию | Описание |
|----------|-------------|----------|
| `replicaCount` | `1` | Количество реплик |
| `autoscaling.enabled` | `true` | Включить HPA |
| `autoscaling.minReplicas` | `1` | Мин. реплик |
| `autoscaling.maxReplicas` | `10` | Макс. реплик |
| `resources.limits.cpu` | `2` | Лимит CPU |
| `resources.limits.memory` | `4Gi` | Лимит памяти |
| `persistence.size` | `10Gi` | Размер PVC для кэша |
| `prometheus.serviceMonitor.enabled` | `true` | ServiceMonitor для Prometheus |

### 6.2. Terraform (Azure AKS)

Модуль Terraform для развёртывания в Azure AKS находится в [`terraform/modules/swarm-aks/`](terraform/modules/swarm-aks/).

Пример использования:

```hcl
module "swarm" {
  source = "./terraform/modules/swarm-aks"

  resource_group_name = "swarm-rg"
  location            = "westeurope"
  cluster_name        = "swarm-aks"
  worker_node_count   = 3
  deploy_monitoring   = true
}
```

Модуль автоматически:
- Создаёт Resource Group
- Разворачивает AKS кластер
- Создаёт Azure Container Registry (ACR)
- Устанавливает Helm-релиз Swarm Worker
- (Опционально) Устанавливает Prometheus и Jaeger

### 6.3. Мониторинг (Prometheus + Grafana)

После установки через Helm с включённым `prometheus.serviceMonitor.enabled=true`, метрики автоматически собираются Prometheus.

Для доступа к Grafana:

```bash
kubectl port-forward -n monitoring svc/prometheus-server 9090:80
```

Откройте http://localhost:9090 и просматривайте метрики `swarm_*`.

Готовый дашборд Grafana находится в [`swarm-scale/monitoring/grafana-dashboard.json`](swarm-scale/monitoring/grafana-dashboard.json).

---

## 7. Окружение и переменные

### 7.1. Обязательные переменные

| Переменная | Описание |
|------------|----------|
| `DEEPSEEK_API_KEY` | API-ключ DeepSeek. Без него система не запустится |
| `ARCHITECT_MODEL` | Модель для агента-архитектора (по умолчанию `deepseek-chat`) |
| `CODER_MODEL` | Модель для агента-кодера (по умолчанию `deepseek-chat`) |
| `REVIEWER_MODEL` | Модель для агента-ревьюера (по умолчанию `deepseek-chat`) |

Если модели не заданы явно — [`ModelSelector`](swarm-scale/src/swarm_scale/model_selector.py:59) выберет их автоматически в зависимости от сложности задачи.

### 7.2. Опциональные переменные

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `MCP_USE_WORKER` | `false` | Использовать SwarmWorker с кэшем, rate limiter и авто-выбором модели |
| `REDIS_URL` | — | URL Redis для L2 распределённого кэша (например, `redis://localhost:6379`) |
| `CACHE_DIR` | `.swarm_cache` | Директория для L1 дискового кэша |
| `L1_TTL` | `3600` | Время жизни L1 кэша (секунды) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | — | gRPC endpoint для OpenTelemetry (Jaeger, SigNoz) |
| `OTEL_ENVIRONMENT` | `development` | Окружение для трассировки |
| `COMPRESSION_ENABLED` | `true` | Включить сжатие промптов через LLMLingua |
| `COMPRESSION_RATE` | `0.5` | Коэффициент сжатия (0.0–1.0). 0.5 = сжатие в 2 раза |
| `COMPRESSION_MIN_TOKENS` | `4096` | Минимальный размер контекста для сжатия |
| `TEMPERATURE` | `0.1` | Температура модели (низкая — для предсказуемости) |
| `MAX_ITERATIONS` | `3` | Максимум циклов Кодер→Ревьюер |

### 7.3. Расширенные переменные

| Переменная | По умолчанию | Описание |
|------------|-------------|----------|
| `GROQ_API_KEY` | — | API-ключ Groq (fallback провайдер при ошибках DeepSeek) |
| `OPENAI_API_KEY` | — | API-ключ OpenAI (второй fallback) |
| `ANTHROPIC_API_KEY` | — | API-ключ Anthropic (третий fallback) |
| `DEEPSEEK_RPM` | `500` | Rate limit для DeepSeek (запросов в минуту) |
| `GROQ_RPM` | `30` | Rate limit для Groq |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com/v1` | Базовый URL API DeepSeek |
| `BASE_URL` | `https://api.deepseek.com/v1` | Базовый URL (общий) |
| `SCALE_CACHE_DIR` | `.swarm_cache` | Директория кэша (swarm-scale) |
| `SCALE_CACHE_SIZE_GB` | `10` | Максимальный размер кэша в ГБ |
| `SCALE_CACHE_TTL_HOURS` | `24` | TTL кэша в часах |
| `SCALE_REDIS_URL` | — | URL Redis (swarm-scale) |
| `SCALE_MAX_WORKERS` | `10` | Максимум параллельных воркеров |
| `SCALE_BATCH_SIZE` | `20` | Размер батча задач |
| `SCALE_RPM_LIMIT` | `500` | Лимит запросов в минуту |
| `SCALE_ENABLE_METRICS` | `true` | Включить Prometheus метрики |
| `SCALE_METRICS_PORT` | `8000` | Порт для HTTP-сервера метрик |
| `SCALE_KAFKA_SERVERS` | — | Kafka brokers для очереди задач |
| `SCALE_KAFKA_INPUT_TOPIC` | `swarm-tasks` | Входной топик Kafka |
| `SCALE_KAFKA_OUTPUT_TOPIC` | `swarm-results` | Выходной топик Kafka |
| `SCALE_POSTGRES_DSN` | — | DSN для PostgreSQL (долгосрочное хранение) |

---

## 8. Примеры

### 8.1. Минимальный: функция сортировки

**Команда:**

```bash
python -m swarm_scale task "Напиши функцию быстрой сортировки (quicksort) на Python"
```

**Что происходит:**

1. **Архитектор**: определяет, что задача простая, создаёт план — одна функция с рекурсивным подходом
2. **Кодер**: пишет реализацию quicksort с pivot-элементом
3. **Ревьюер** (если сложность не `low`): проверяет, что функция работает корректно

**Результат** (сокращённо):

```python
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)
```

### 8.2. Средний: REST API для блога

**Команда:**

```bash
python -m swarm_scale task \
  "Создай REST API для блога на FastAPI: CRUD для постов, SQLite, Pydantic схемы" \
  --json
```

**Что происходит:**

1. Модель классифицирует сложность как `medium` (ключевые слова: `api`, `crud`)
2. **Архитектор**: проектирует структуру:
   - Модель `Post` (id, title, content, created_at, updated_at)
   - Роуты `GET/POST/PUT/DELETE /posts`
   - SQLite через SQLAlchemy
3. **Кодер**: реализует полный код
4. **Ревьюер**: проверяет валидацию Pydantic, обработку ошибок, типы

**Результат** — готовый файл `main.py` для FastAPI:

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import sqlite3, datetime

app = FastAPI(title="Blog API")

class PostCreate(BaseModel):
    title: str
    content: str

class Post(PostCreate):
    id: int
    created_at: datetime.datetime
    updated_at: datetime.datetime

@app.get("/posts", response_model=List[Post])
async def list_posts():
    # ...
```

### 8.3. Сложный: микросервис с Kafka

**Команда:**

```bash
python -m swarm_scale task \
  "Реализуй микросервис обработки заказов: FastAPI + Kafka producer/consumer + PostgreSQL" \
  --repo myorg/orders-service --file src/main.py
```

**Что происходит:**

1. Система определяет сложность как `high` (ключевые слова: `microservice`, `kafka`, `database`)
2. Используется `deepseek-reasoner` для архитектора
3. **Архитектор** детально проектирует:
   - FastAPI приложение с роутами
   - Kafka producer для отправки заказов
   - Kafka consumer для обработки
   - SQLAlchemy модели для PostgreSQL
4. **Кодер** реализует каждый компонент
5. **Ревьюер** проводит тщательную проверку

**Результат** — структура микросервиса:

```
orders-service/
├── main.py          # FastAPI приложение
├── models.py        # SQLAlchemy модели
├── schemas.py       # Pydantic схемы
├── producer.py      # Kafka producer
├── consumer.py      # Kafka consumer
└── database.py      # Подключение к БД
```

---

## 9. Мониторинг

### 9.1. Prometheus метрики

Swarm экспортирует метрики в Prometheus формате на порту `8000` (настраивается через `SCALE_METRICS_PORT`).

**Доступные метрики:**

| Метрика | Тип | Описание |
|---------|-----|----------|
| `swarm_tasks_processed_total` | Counter | Всего обработанных задач |
| `swarm_tasks_cached_total` | Counter | Задач взято из кэша |
| `swarm_tasks_errors_total` | Counter | Задач с ошибками |
| `swarm_cache_hits_total{layer="l1"}` | Counter | Попаданий в L1 кэш |
| `swarm_cache_hits_total{layer="l2"}` | Counter | Попаданий в L2 кэш |
| `swarm_cache_misses_total{layer="l1"}` | Counter | Промахов L1 кэша |
| `swarm_cache_misses_total{layer="l2"}` | Counter | Промахов L2 кэша |
| `swarm_cache_latency_seconds` | Histogram | Задержки кэша |
| `swarm_cache_hit_ratio` | Gauge | Hit ratio по слоям |

Пример запроса PromQL — hit ratio L1 кэша:

```promql
rate(swarm_cache_hits_total{layer="l1"}[5m])
/
(rate(swarm_cache_hits_total{layer="l1"}[5m]) + rate(swarm_cache_misses_total{layer="l1"}[5m]))
```

Конфигурация Prometheus для сбора метрик находится в [`swarm-scale/monitoring/prometheus.yml`](swarm-scale/monitoring/prometheus.yml).

### 9.2. Grafana дашборд

Готовый дашборд Grafana — [`swarm-scale/monitoring/grafana-dashboard.json`](swarm-scale/monitoring/grafana-dashboard.json).

Импортируйте его в Grafana:

1. Откройте Grafana → **+** → **Import**
2. Загрузите файл `grafana-dashboard.json` или вставьте его содержимое
3. Выберите источник данных Prometheus
4. Нажмите **Import**

Дашборд включает панели:
- Количество обработанных задач (rate)
- Hit ratio кэша (L1 и L2)
- Распределение сложности задач
- Задержки обработки
- Количество ошибок

### 9.3. OpenTelemetry + Jaeger

Swarm поддерживает распределённую трассировку через OpenTelemetry.

**Настройка:**

```bash
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
export OTEL_ENVIRONMENT=production
```

**Собираемые spans:**

| Span | Описание |
|------|----------|
| `swarm.run` | Полный цикл роя |
| `swarm.stream` | Пошаговый вывод |
| `worker.process_task` | Обработка задачи воркером |
| `worker.cache_check` | Проверка кэша |
| `worker.rate_limiter` | Ожидание rate limiter |
| `worker.run_swarm` | Запуск SwarmRunner |
| `cache.get` / `cache.set` | Операции кэша |

**Jaeger UI:**

```bash
# Через Docker Compose (см. раздел 5.3)
docker compose up -d jaeger
# Откройте http://localhost:16686
```

---

## 10. Часто задаваемые вопросы (FAQ)

### 1. Почему задача не выполняется?

**Проверьте:**
- Указан ли [`DEEPSEEK_API_KEY`](.env.example:2) в файле `.env` или в переменных окружения
- Доступен ли интернет до `api.deepseek.com`
- Не превышен ли лимит запросов (см. `DEEPSEEK_RPM`)

При ошибке в MCP-сервере вы увидите:

```
ERROR: DEEPSEEK_API_KEY not configured.
Create a .env file in the project root with:
DEEPSEEK_API_KEY=your_api_key_here
```

### 2. Как ускорить выполнение?

- **Включите MCP_USE_WORKER=true** — включит кэш. Повторные задачи будут возвращаться мгновенно
- **Используйте complexity=low** для простых задач (тесты, документация) — ревьюер отключается, экономя один вызов API
- **Подключите Redis** — кэш будет общим между запусками
- **Увеличьте MAX_ITERATIONS** — если код часто отклоняется, больше итераций = больше шансов на APPROVED (но дольше)

### 3. Сколько это стоит?

Стоимость зависит от:
- **Сложности задачи**: `low` ≈ 2 вызова API (Architect + Coder), `medium` ≈ 3 вызова (+ Reviewer), `critical` ≈ 3 вызова через reasoning-модель
- **Длины контекста**: длинные ТЗ = больше токенов
- **Количества итераций**: каждое отклонение ревьюера = ещё один цикл Coder + Reviewer

В среднем:
- Простая задача (калькулятор): ~5–10K токенов
- Средняя (REST API): ~20–50K токенов
- Сложная (микросервис): ~100–300K токенов

### 4. Что делать при ошибке 429?

Ошибка `429 Too Many Requests` означает превышение rate limit DeepSeek.

**Автоматически:** [`AdaptiveRateLimiter`](swarm-scale/src/swarm_scale/rate_limiter.py) отслеживает 429 ошибки и автоматически снижает частоту запросов.

**Вручную:** уменьшите значение `DEEPSEEK_RPM` (по умолчанию 500) в `.env`:

```ini
DEEPSEEK_RPM=100
```

### 5. Как добавить свой API-ключ?

**Через MCP:** параметр `DEEPSEEK_API_KEY` в `env` секции [`.roo/mcp.json`](.roo/mcp.json).

**Через `.env`:** укажите в файле [`.env`](.env.example):

```ini
DEEPSEEK_API_KEY=sk-ваш_ключ
```

**Через переменные окружения:**

```bash
export DEEPSEEK_API_KEY=sk-ваш_ключ
```

### 6. Как добавить fallback-провайдер?

Укажите дополнительные API-ключи в `.env`:

```ini
GROQ_API_KEY=gsk_ваш_ключ
OPENAI_API_KEY=sk-ваш_ключ_openai
```

При ошибке DeepSeek система автоматически переключится на Groq (модель `llama3-70b-8192`), затем на OpenAI.

### 7. Как очистить кэш?

**L1 (дисковый кэш):**

```bash
rm -rf .swarm_cache
```

**L2 (Redis):**

```bash
redis-cli KEYS "swarm:*" | xargs redis-cli DEL
```

Или настройте меньший `L1_TTL` / `SCALE_CACHE_TTL_HOURS`.

### 8. Работает ли Swarm без интернета?

Нет. Swarm использует облачные LLM API (DeepSeek, Groq, OpenAI). Для работы требуется постоянное интернет-соединение.

Однако если задача уже была выполнена и результат закэширован — повторный запрос вернёт результат из кэша без обращения к API.

---

## 11. Устранение неполадок

### 11.1. Логи

Логи пишутся в stderr/stdout. Для подробного вывода используйте флаг `-v`:

```bash
python -m swarm_scale -v task "Напиши тест"
```

Уровни логирования:
- `INFO` — основные события: запуск, завершение, попадание в кэш
- `WARNING` — некритичные проблемы: недоступность Redis, fallback провайдера
- `ERROR` — ошибки: неверный API-ключ, таймауты, сбои агентов
- `DEBUG` (с `-v`) — детальная информация: каждый вызов LLM, результаты сжатия

### 11.2. Rate limiting

Система содержит встроенный [`AdaptiveRateLimiter`](swarm-scale/src/swarm_scale/rate_limiter.py), который:

1. Ограничивает количество запросов к API согласно `DEEPSEEK_RPM` / `GROQ_RPM`
2. При получении ошибки `429` автоматически снижает частоту запросов
3. Постепенно восстанавливает частоту при успешных запросах

Если лимиты кажутся вам слишком строгими — увеличьте значения в `.env`:

```ini
DEEPSEEK_RPM=1000
GROQ_RPM=60
```

### 11.3. Fallback-провайдеры

При недоступности DeepSeek система переключается на резервные провайдеры.

**Цепочка fallback:**

```
DeepSeek (основной) → Groq (fallback №1) → OpenAI (fallback №2)
```

**Как проверить, какой провайдер используется:**

```bash
python -m swarm_scale -v task "test" 2>&1 | findstr "fallback"
```

Или в логах:

```
[WARNING] DeepSeek unavailable, falling back to Groq
```

### 11.4. Кэш

**Проверка состояния кэша:**

```bash
python -m swarm_scale task "test task"
# В конце вывода:
# Статистика воркера: processed=5, cached=3, errors=0
```

`cached=3` означает, что 3 из 5 задач были взяты из кэша и не потребовали вызова API.

**Если кэш не работает:**
- Убедитесь, что `MCP_USE_WORKER=true` (без этого кэш отключён)
- Проверьте права на запись в директорию `.swarm_cache`
- Для Redis: проверьте доступность `REDIS_URL`

---

*Документация подготовлена для пользователей Swarm. Если вы нашли ошибку или хотите предложить улучшение — создайте issue в репозитории проекта.*
