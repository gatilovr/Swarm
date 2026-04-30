# Swarm Dev Guide

**Требование**: мин. токенов, макс. качество. Всё по существу.

---

## 1. Модули и зависимости

| Модуль | Путь | Назначение | Зависит от |
|--------|------|-----------|------------|
| `swarm` | [`swarm/`](swarm/) | Ядро: агенты, граф, LLM провайдер | litellm, langgraph, opentelemetry-api |
| `swarm-mcp` | [`swarm-mcp/`](swarm-mcp/) | MCP сервер для Roo Code | swarm, mcp |
| `swarm-scale` | [`swarm-scale/`](swarm-scale/) | Масштабирование: кэш, worker, rate limiter | swarm, prometheus_client, redis |

**Граф зависимостей:**
```
swarm-mcp → swarm
swarm-scale → swarm
swarm-scale -/-> swarm-mcp (не зависит)
```

---

## 2. Архитектура

### 2.1. Поток выполнения

```
Task → MCP/CLI → SwarmRunner → StateGraph
                                   ├── ArchitectAgent (план)
                                   ├── CoderAgent (код)
                                   └── ReviewerAgent (ревью) → CoderAgent (цикл) или ✅
                                   Result → Cache → Response
```

### 2.2. Ключевые файлы

| Компонент | Файл | Ключевые методы |
|-----------|------|----------------|
| Базовый агент | [`swarm/agents/base.py`](swarm/agents/base.py) | `process(state)`, `_call_llm(messages)` |
| Architect | [`swarm/agents/architect.py`](swarm/agents/architect.py) | `process(state)` → план |
| Coder | [`swarm/agents/coder.py`](swarm/agents/coder.py) | `process(state)` → код |
| Reviewer | [`swarm/agents/reviewer.py`](swarm/agents/reviewer.py) | `process(state)` → APPROVED/REJECTED |
| LLM провайдер | [`swarm/llm/base.py`](swarm/llm/base.py) | `generate(messages, model, temperature, max_tokens) -> LLMResponse` |
| LiteLLM impl | [`swarm/llm/litellm_provider.py`](swarm/llm/litellm_provider.py) | Router с fallback DeepSeek → Groq |
| Граф | [`swarm/graph/workflow.py`](swarm/graph/workflow.py) | `create_swarm_graph(config)` |
| Runner | [`swarm/main.py`](swarm/main.py) | `run(task)`, `stream(task)` (оба async) |
| MCP сервер | [`swarm-mcp/src/swarm_mcp/server.py`](swarm-mcp/src/swarm_mcp/server.py) | `call_tool(name, arguments)` |
| Worker | [`swarm-scale/src/swarm_scale/worker.py`](swarm-scale/src/swarm_scale/worker.py) | `process_task(task)`, `process_batch(tasks)` |
| Кэш | [`swarm-scale/src/swarm_scale/cache.py`](swarm-scale/src/swarm_scale/cache.py) | `get(task, profile_id)`, `set(task, result, profile_id)` |
| Rate limiter | [`swarm-scale/src/swarm_scale/rate_limiter.py`](swarm-scale/src/swarm_scale/rate_limiter.py) | `acquire()`, `release()` (async) |
| Model selector | [`swarm-scale/src/swarm_scale/model_selector.py`](swarm-scale/src/swarm_scale/model_selector.py) | `select(content, force_complexity) -> ModelConfig` |
| Компрессия | [`swarm/compression.py`](swarm/compression.py) | `compress_messages(messages, rate) -> messages` |
| Трассировка | [`swarm/tracing.py`](swarm/tracing.py) | `setup_tracing(service_name)`, `get_tracer(name)` |
| Метрики | [`swarm-scale/src/swarm_scale/metrics.py`](swarm-scale/src/swarm_scale/metrics.py) | SwarmMetrics (singleton) |
| Конфиг (core) | [`swarm/config.py`](swarm/config.py) | `SwarmConfig.from_env()` |
| Конфиг (LLM) | [`swarm/llm/config.py`](swarm/llm/config.py) | `LiteLLMConfig.from_env()` |
| Конфиг (scale) | [`swarm-scale/src/swarm_scale/config.py`](swarm-scale/src/swarm_scale/config.py) | `ScaleConfig.from_env()` |

---

## 3. Контракты и интерфейсы

### 3.1. [`BaseLLMProvider`](swarm/llm/base.py:30)

```python
class BaseLLMProvider(ABC):
    async def generate(
        self, messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...

    def count_tokens(self, messages: list[dict[str, str]], model: str | None = None) -> int: ...

    @property
    def provider_name(self) -> str: ...
```

### 3.2. [`LLMResponse`](swarm/llm/base.py:8)

```python
@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_seconds: float = 0.0
```

### 3.3. [`SwarmState`](swarm/state.py:8)

```python
class SwarmState(TypedDict):
    messages: Annotated[list, add_messages]  # LangGraph reducer
    task: str
    plan: str
    code: str
    review_result: str
    iteration: int
    max_iterations: int
    is_final: bool
```

### 3.4. [`Task`](swarm-scale/src/swarm_scale/task.py:27) / [`TaskResult`](swarm-scale/src/swarm_scale/task.py:89)

```python
@dataclass
class Task:
    task_id: str
    content: str
    repository: str = ""
    file_path: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    project_profile_id: str | None = None
    max_cost_cents: float = 5.0
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: TaskStatus = TaskStatus.PENDING
    complexity_hint: str | None = None
    project_files: int = 0

@dataclass
class TaskResult:
    task_id: str
    plan: str = ""
    code: str = ""
    review_result: str = ""
    approved: bool = False
    iterations: int = 1
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_sec: float = 0.0
    cached: bool = False
    error: str | None = None
    completed_at: datetime = field(default_factory=datetime.utcnow)
```

### 3.5. [`ModelConfig`](swarm-scale/src/swarm_scale/model_selector.py:13)

```python
@dataclass
class ModelConfig:
    architect: str = "deepseek-chat"
    coder: str = "deepseek-chat"
    reviewer: str | None = "deepseek-chat"
    skip_review: bool = False
    temperature: float = 0.1
    provider: str = "litellm"
    display_name: str = ""
```

---

## 4. ADR (Architecture Decision Records)

| ID | Решение | Альтернативы | Обоснование | Файл |
|----|---------|-------------|-------------|------|
| ADR-001 | LiteLLM Router с fallback | Прямой OpenAI client | Автоматический fallback DeepSeek→Groq, latency-based routing | [`swarm/llm/litellm_provider.py`](swarm/llm/litellm_provider.py) |
| ADR-002 | LangGraph StateGraph | CrewAI, AutoGPT | Стандарт индустрии, reducer-функции, checkpointing | [`swarm/graph/workflow.py`](swarm/graph/workflow.py) |
| ADR-003 | async везде | sync + ThreadPoolExecutor | Единый async stack от LLM до графа | [`swarm/agents/base.py`](swarm/agents/base.py) |
| ADR-004 | SwarmPromptCompressor с graceful fallback | Всегда сжимать | LLMLingua не обязательна, fallback без сжатия | [`swarm/compression.py`](swarm/compression.py) |
| ADR-005 | Singleton SwarmMetrics | DI | Prometheus registry глобален по определению | [`swarm-scale/src/swarm_scale/metrics.py`](swarm-scale/src/swarm_scale/metrics.py) |
| ADR-006 | Helm chart + Terraform | Только kustomization | Helm — стандарт для K8s, Terraform — для облака | [`charts/swarm-worker/`](charts/swarm-worker/) |
| ADR-007 | `copy.deepcopy` для race condition | Lock | deepcopy проще и безопаснее блокировок | [`swarm-scale/src/swarm_scale/worker.py:110`](swarm-scale/src/swarm_scale/worker.py:110) |
| ADR-008 | `MCP_USE_WORKER` env var | Всегда worker | Совместимость с простыми случаями | [`swarm-mcp/src/swarm_mcp/config.py:31`](swarm-mcp/src/swarm_mcp/config.py:31) |

---

## 5. Как добавить нового LLM провайдера

1. Создай класс, наследующий [`BaseLLMProvider`](swarm/llm/base.py:30)
2. Реализуй `generate()` и `count_tokens()`
3. Добавь провайдера в Router в [`LiteLLMProvider`](swarm/llm/litellm_provider.py):
```python
{
    "model_name": "my-model",
    "litellm_params": {
        "model": "provider/my-model",
        "api_key": os.getenv("MY_API_KEY"),
    },
}
```

## 6. Как добавить новый кэш-слой (L3)

1. Реализуй интерфейс уровня в [`CacheManager`](swarm-scale/src/swarm_scale/cache.py:118):
   - `get(key) -> dict | None`
   - `set(key, data, expire) -> None`
2. Добавь слой в цепочку `_do_get()`: `L1 → L2 → L3`
3. Добавь Prometheus метрики в [`metrics.py`](swarm-scale/src/swarm_scale/metrics.py)
4. Добавь span в [`tracing.py`](swarm/tracing.py)

---

## 7. Тестирование

| Тип | Инструмент | Команда | Файлов |
|-----|-----------|---------|--------|
| Unit (core) | pytest | `pytest swarm/tests/ -v` | 4 |
| Unit (scale) | pytest | `pytest swarm-scale/tests/ -v` | 14 |
| Unit (mcp) | pytest | `pytest swarm-mcp/tests/ -v` | 1 |
| Property-based | hypothesis | `pytest tests/*_properties.py -v` | 4 |
| Code style | ruff | `ruff check .` | — |
| Types | mypy | `mypy swarm/` | — |

**Все тесты:** `pytest swarm/ swarm-mcp/ swarm-scale/ -v`

---

## 8. CI/CD

| Шаг | Job | Файл | Блокирует? |
|-----|-----|------|-----------|
| Lint (ruff) | `lint` | [`ci.yml`](.github/workflows/ci.yml) | ✅ |
| Test (3 модуля, matrix) | `test` | [`ci.yml`](.github/workflows/ci.yml) | ✅ (после lint) |
| Import check | `import-check` | [`ci.yml`](.github/workflows/ci.yml) | ✅ (после lint) |
| Secret scan | `gitleaks` | [`ci.yml`](.github/workflows/ci.yml) | ✅ |
| SBOM (CycloneDX) | `sbom` | [`security.yml`](.github/workflows/security.yml) | ❌ (еженедельно) |
| Dependency audit | `dependency-audit` | [`security.yml`](.github/workflows/security.yml) | ❌ (еженедельно) |
| Docker build | `docker` | [`ci.yml`](.github/workflows/ci.yml) | ✅ (после test+gitleaks, только main) |

---

## 9. Security

- **API ключи**: только в `.env` или Kubernetes Secrets
- **Secret scanning**: Gitleaks в CI ([`.gitleaks.toml`](.gitleaks.toml))
- **SBOM**: CycloneDX (`sbom-*.json`)
- **Dependency audit**: pip-audit еженедельно
- **Запрещено**: коммитить `.env`, hardcode API keys

---

## 10. Метрики (Prometheus)

| Метрика | Тип | Labels | Файл |
|---------|-----|--------|------|
| `swarm_tasks_total` | Counter | status | [`metrics.py`](swarm-scale/src/swarm_scale/metrics.py:18) |
| `swarm_task_duration_seconds` | Histogram | — | [`metrics.py`](swarm-scale/src/swarm_scale/metrics.py:24) |
| `swarm_tokens_total` | Counter | model | [`metrics.py`](swarm-scale/src/swarm_scale/metrics.py:31) |
| `swarm_cost_usd_total` | Counter | — | [`metrics.py`](swarm-scale/src/swarm_scale/metrics.py:37) |
| `swarm_active_workers` | Gauge | — | [`metrics.py`](swarm-scale/src/swarm_scale/metrics.py:43) |
| `swarm_queue_depth` | Gauge | — | [`metrics.py`](swarm-scale/src/swarm_scale/metrics.py:48) |
| `swarm_cache_hits_total` | Counter | layer | [`metrics.py`](swarm-scale/src/swarm_scale/metrics.py:65) |
| `swarm_cache_misses_total` | Counter | layer | [`metrics.py`](swarm-scale/src/swarm_scale/metrics.py:71) |
| `swarm_cache_latency_seconds` | Histogram | operation, layer | [`metrics.py`](swarm-scale/src/swarm_scale/metrics.py:83) |
| `swarm_cache_hit_ratio` | Gauge | layer | [`metrics.py`](swarm-scale/src/swarm_scale/metrics.py:90) |

---

## 11. Трассировка (OpenTelemetry)

| Span | Родитель | Где создаётся |
|------|----------|-------------|
| `swarm.run` | — | [`swarm/main.py:43`](swarm/main.py:43) |
| `swarm.stream` | — | [`swarm/main.py:98`](swarm/main.py:98) |
| `{Agent}._call_llm` | swarm.run | [`swarm/agents/base.py:82`](swarm/agents/base.py:82) |
| `worker.process_task` | — | [`swarm-scale/src/swarm_scale/worker.py:56`](swarm-scale/src/swarm_scale/worker.py:56) |
| `worker.cache_check` | worker.process_task | [`swarm-scale/src/swarm_scale/worker.py:80`](swarm-scale/src/swarm_scale/worker.py:80) |
| `worker.rate_limiter` | worker.process_task | [`swarm-scale/src/swarm_scale/worker.py:102`](swarm-scale/src/swarm_scale/worker.py:102) |
| `worker.run_swarm` | worker.process_task | [`swarm-scale/src/swarm_scale/worker.py:119`](swarm-scale/src/swarm_scale/worker.py:119) |
| `cache.get` | parent | [`swarm-scale/src/swarm_scale/cache.py:151`](swarm-scale/src/swarm_scale/cache.py:151) |
| `cache.set` | parent | [`swarm-scale/src/swarm_scale/cache.py:227`](swarm-scale/src/swarm_scale/cache.py:227) |
| `ratelimiter.acquire` | parent | [`swarm-scale/src/swarm_scale/rate_limiter.py:44`](swarm-scale/src/swarm_scale/rate_limiter.py:44) |

---

## 12. Конфигурация

См. [`.env.example`](.env.example), [`SwarmConfig`](swarm/config.py:13), [`LiteLLMConfig`](swarm/llm/config.py:9), [`ScaleConfig`](swarm-scale/src/swarm_scale/config.py:11).

| Переменная | Тип | По умолч. | Источник |
|-----------|-----|-----------|----------|
| `DEEPSEEK_API_KEY` | str | — | [`swarm/llm/config.py:55`](swarm/llm/config.py:55) |
| `ARCHITECT_MODEL` | str | deepseek-chat | [`swarm/config.py:50`](swarm/config.py:50) |
| `CODER_MODEL` | str | deepseek-chat | [`swarm/config.py:51`](swarm/config.py:51) |
| `REVIEWER_MODEL` | str | deepseek-chat | [`swarm/config.py:52`](swarm/config.py:52) |
| `MCP_USE_WORKER` | bool | false | [`swarm-mcp/src/swarm_mcp/config.py:31`](swarm-mcp/src/swarm_mcp/config.py:31) |
| `COMPRESSION_RATE` | float | 0.5 | [`swarm/llm/config.py:63`](swarm/llm/config.py:63) |
| `COMPRESSION_ENABLED` | bool | true | [`swarm/llm/config.py:62`](swarm/llm/config.py:62) |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | str | — | [`swarm/tracing.py:59`](swarm/tracing.py:59) |
| `DEEPSEEK_RPM` | int | 500 | [`swarm/llm/config.py:60`](swarm/llm/config.py:60) |
| `SCALE_CACHE_DIR` | str | .swarm_cache | [`swarm-scale/src/swarm_scale/config.py:83`](swarm-scale/src/swarm_scale/config.py:83) |
| `SCALE_CACHE_TTL_HOURS` | int | 24 | [`swarm-scale/src/swarm_scale/config.py:85`](swarm-scale/src/swarm_scale/config.py:85) |
| `SCALE_RPM_LIMIT` | int | 500 | [`swarm-scale/src/swarm_scale/config.py:89`](swarm-scale/src/swarm_scale/config.py:89) |

---

## 13. Kubernetes (Helm)

```bash
# Установка
helm install swarm-worker ./charts/swarm-worker \
  --set env.DEEPSEEK_API_KEY=sk-xxx

# Terraform (Azure)
terraform apply -var="cluster_name=my-swarm" -var="extra_env_vars.DEEPSEEK_API_KEY=sk-xxx"
```

См. [`charts/swarm-worker/values.yaml`](charts/swarm-worker/values.yaml) для всех опций.

---

## 14. Известные проблемы

| Проблема | Причина | Статус |
|----------|---------|--------|
| `test_cache_stats` PermissionError на Windows | tempfile cleanup | Workaround: `shutil.rmtree` в finally |
| Python 3.14: `compression` конфликт имён | Новый stdlib модуль `compression` | Переименовать в `prompt_compression` |
| Singleton SwarmMetrics в тестах | Глобальный Prometheus registry | Пересоздавать registry между тестами |
