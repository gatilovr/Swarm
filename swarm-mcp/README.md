# Swarm MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Swarm MCP Server (v2.0)** — это продуктовый MCP-сервер, который предоставляет Roo Code 5 высокоуровневых инструментов для работы с роем AI-агентов.

Внутри сервера работают три AI-агента, выполняющих полный цикл разработки:

1. **🏗️ Архитектор** — анализирует ТЗ и создаёт план
2. **💻 Кодер** — пишет код по плану
3. **🔍 Ревьюер** — проверяет код (APPROVED/REJECTED, до 3 итераций)

---

## Содержание

- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
- [Инструменты MCP](#инструменты-mcp)
- [Безопасность](#безопасность)
- [Архитектура](#архитектура)
- [Разработка](#разработка)
- [Docker](#docker)
- [Лицензия](#лицензия)

---

## Установка

### Требования

- Python 3.10 или выше
- API-ключ [DeepSeek](https://platform.deepseek.com/)

### Из исходников

```bash
git clone <your-repo-url>
cd swarm-mcp
pip install -e .
```

### Через pip (если опубликован)

```bash
pip install swarm-mcp
```

### Через Docker

```bash
docker build -t swarm-mcp .
docker run -e DEEPSEEK_API_KEY=your_key_here swarm-mcp
```

---

## Быстрый старт

### 1. Настройка окружения

Создайте файл `.env` в корне проекта:

```env
DEEPSEEK_API_KEY=sk-your-deepseek-api-key-here
```

### 2. Запуск сервера

```bash
python -m swarm_mcp
```

Сервер запустится в режиме `stdio` и будет ожидать MCP-сообщений из stdin.

### 3. Подключение к Roo Code

Добавьте MCP-сервер в конфигурацию Roo Code (файл `.roo/mcp.json`):

```json
{
  "mcpServers": {
    "swarm": {
      "command": "python",
      "args": ["-m", "swarm_mcp"],
      "env": {
        "DEEPSEEK_API_KEY": "sk-your-api-key"
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

После подключения все 5 инструментов будут доступны в Roo Code.

### 4. Использование

Задача для роя формулируется как техническое задание:

> "Напиши функцию на Python для быстрой сортировки (quicksort) с комментариями"

Или более сложная:

> "Создай FastAPI-приложение с тремя endpoint'ами: GET /items, POST /items, DELETE /items/{id}. Используй SQLite для хранения данных."

---

## Конфигурация

### Переменные окружения

| Переменная | Описание | По умолчанию |
|-----------|----------|-------------|
| `DEEPSEEK_API_KEY` | API-ключ DeepSeek **(обязательно)** | — |
| `MCP_ORCHESTRATION` | Включить инструменты оркестрации (`swarm_status`, `swarm_ask` и др.) | `true` |
| `MCP_ENABLE_EXECUTOR` | Включить `swarm_execute` | `true` |
| `ARCHITECT_MODEL` | Модель для архитектора | `deepseek-chat` |
| `CODER_MODEL` | Модель для кодера | `deepseek-chat` |
| `REVIEWER_MODEL` | Модель для ревьюера | `deepseek-chat` |
| `BASE_URL` | Базовый URL API DeepSeek | `https://api.deepseek.com/v1` |
| `TEMPERATURE` | Температура модели (0.0–1.0) | `0.1` |
| `MAX_ITERATIONS` | Максимум циклов кодер→ревьюер | `3` |

### Пример `.env`

```env
DEEPSEEK_API_KEY=sk-your-key-here
MCP_ORCHESTRATION=true
ARCHITECT_MODEL=deepseek-chat
CODER_MODEL=deepseek-chat
REVIEWER_MODEL=deepseek-chat
BASE_URL=https://api.deepseek.com/v1
TEMPERATURE=0.1
MAX_ITERATIONS=3
```

---

## Инструменты MCP

Сервер предоставляет 5 инструментов для Roo Code:

### `run_swarm`

Запускает полный цикл разработки: Архитектор → Кодер → Ревьюер (с циклом доработки).

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|-------------|-------------|----------|
| `task` | `string` | ✅ | — | Детальное техническое задание |
| `context` | `string` | ❌ | `""` | Дополнительный контекст (файлы, архитектура) |
| `mode` | `enum` | ❌ | `full` | `full` — полный цикл, `plan` — только план |
| `complexity` | `enum` | ❌ | `auto` | `auto` / `low` / `medium` / `high` / `critical` |
| `project_files` | `int` | ❌ | `0` | Примерное количество файлов в проекте |

**Формат ответа (JSON):**

```json
{
  "status": "success",
  "summary": "Код написан и прошёл ревью с 1 итерации",
  "plan": "1. Создать функцию...",
  "code": "def quicksort(arr): ...",
  "review": "APPROVED",
  "iterations": 1,
  "files": ["examples/quicksort.py"],
  "cached": false,
  "tokens": {
    "total": 1520,
    "prompt": 850,
    "completion": 670
  }
}
```

### `swarm_status`

Показывает состояние проекта: структуру, файлы, тесты, git-статус.

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|-------------|-------------|----------|
| `scope` | `enum` | ❌ | `summary` | `summary` — кратко, `full` — детально |

**Пример ответа:**

```json
{
  "project_name": "Swarm",
  "total_files": 95,
  "total_lines": 12500,
  "test_files": 18,
  "languages": {"Python": 85, "YAML": 5, "Markdown": 5},
  "git_branch": "main",
  "git_clean": true
}
```

### `swarm_ask`

Задаёт вопрос о проекте и получает структурированный ответ.

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|-------------|-------------|----------|
| `question` | `string` | ✅ | — | Вопрос на естественном языке |
| `files` | `string[]` | ❌ | — | Ограничить анализ конкретными файлами |

**Поддерживаемые категории вопросов:**
- Архитектура: «какая архитектура?», «как устроен проект?»
- Зависимости: «какие библиотеки используются?»
- Безопасность: «есть ли уязвимости?», «как с аутентификацией?»
- Производительность: «где узкое место?»
- Тесты: «какие есть тесты?», «какое покрытие?»
- Качество кода: «как улучшить код?»
- Документация: «есть ли документация?»
- Конфигурация: «какие настройки?»
- Общие: «что это за проект?»

### `swarm_execute`

Безопасно выполняет команду терминала с проверкой по политикам безопасности.

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|-------------|-------------|----------|
| `command` | `string` | ✅ | — | Команда для выполнения |
| `timeout` | `int` | ❌ | `60` | Таймаут в секундах (макс. 300) |
| `approved` | `bool` | ❌ | `false` | Предварительное одобрение |

**Внимание:** Этот инструмент требует явного одобрения пользователя (не в `alwaysAllow`).

### `swarm_files`

Читает содержимое файлов по glob-паттерну.

| Параметр | Тип | Обязательный | По умолчанию | Описание |
|----------|-----|-------------|-------------|----------|
| `pattern` | `string` | ✅ | — | Glob-паттерн (например, `**/*.py`) |
| `max_lines` | `int` | ❌ | `100` | Максимум строк на файл |

---

## Безопасность

`swarm_execute` имеет 4-уровневую систему безопасности:

1. **System Prompt** — ограничения на уровне промпта Roo Code
2. **`.swarm-policy.toml`** — файл политик в корне проекта (3 уровня: `auto_allow`, `require_approval`, `deny`)
3. **CommandSanitizer** — кодовая проверка команд (case-insensitive, частичное совпадение)
4. **Roo Code approval** — пользователь явно подтверждает `swarm_execute`

### Политики по умолчанию

| Уровень | Команды |
|---------|---------|
| ✅ `auto_allow` | `pip install`, `pytest`, `git status`, `git diff`, `git log`, `ls`, `dir`, `type`, `find`, `echo` |
| ⚠️ `require_approval` | `git push`, `git commit`, `git merge`, `rm`, `del`, `mv`, `move`, `copy`, `cp`, `mkdir`, `sudo`, `npm publish` |
| 🚫 `deny` | `rm -rf /`, `chmod 777`, `format C:`, `del /F /S`, `> /dev/sda`, `:(){ :\|:& };:` |

---

## Архитектура

```
┌──────────────────────────────────────────────────────────────┐
│                    Roo Code (MCP Client)                       │
└──────────────────────┬───────────────────────────────────────┘
                       │ JSON-RPC (stdio)
┌──────────────────────▼───────────────────────────────────────┐
│                    swarm-mcp (MCP Server v2.0)                 │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  call_tool handler                                       │  │
│  │  ┌──────────┐ ┌──────────┐ ┌────────┐ ┌───────────┐   │  │
│  │  │run_swarm │ │swarm_stat│ │swarm_ │ │swarm_exec │   │  │
│  │  │          │ │us        │ │ask    │ │ute        │   │  │
│  │  └────┬─────┘ └────┬─────┘ └───┬────└─────┬─────┘   │  │
│  │       │             │           │          │          │  │
│  │  ┌────▼─────┐ ┌────▼─────┐ ┌───▼────┐ ┌───▼──────┐  │  │
│  │  │SwarmRunn │ │ProjectSt │ │Project │ │CommandEx │  │  │
│  │  │er        │ │atus      │ │QA      │ │ecutor    │  │  │
│  │  │          │ │          │ │        │ │          │  │  │
│  │  │ ┌──────┐ │ │┌───────┐ │ │┌──────┐│ │┌────────┐│  │  │
│  │  │ │Archit│ │ ││Files  │ │ ││Categ ││ ││Sanitiz ││  │  │
│  │  │ │-ector│ │ ││Git    │ │ ││ories ││ ││er      ││  │  │
│  │  │ │Coder │ │ ││Tests  │ │ ││Answer││ ││Policy  ││  │  │
│  │  │ │Review│ │ ││Config │ │ ││s     ││ ││        ││  │  │
│  │  │ │er    │ │ │└───────┘ │ │└──────┘│ │└────────┘│  │  │
│  │  │ └──────┘ │ └─────────┘ └────────┘ └──────────┘  │  │
│  │  └──────────┘                                       │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  Config: config.py    Cache: CacheManager    Queue: Queue      │
└──────────────────────────────────────────────────────────────┘
```

### Компоненты

1. **MCP Server Layer** ([`server.py`](src/swarm_mcp/server.py)) — обрабатывает MCP-запросы, маршрутизирует к 5 хендлерам
2. **Config Layer** ([`config.py`](src/swarm_mcp/config.py)) — MCPConfig с флагами `orchestration_enabled`, `enable_executor`
3. **Swarm Runner** ([`swarm/main.py`](../swarm/main.py)) — ядро роя: граф LangGraph с тремя агентами
4. **Status** ([`status.py`](src/swarm_mcp/status.py)) — анализ состояния проекта
5. **Ask** ([`ask.py`](src/swarm_mcp/ask.py)) — ответы на вопросы о проекте (9 категорий)
6. **Executor** ([`executor.py`](src/swarm_mcp/executor.py)) — безопасный запуск команд с политиками
7. **Policy** ([`policy.py`](src/swarm_mcp/policy.py)) — загрузка политик безопасности из `.swarm-policy.toml`

---

## Разработка

### Установка для разработки

```bash
cd swarm-mcp
pip install -e .
pip install pytest pytest-asyncio
```

### Запуск тестов

```bash
cd swarm-mcp
pytest tests/ -v
```

### Структура проекта

```
swarm-mcp/
├── Dockerfile                      # Docker-образ
├── LICENSE                         # MIT лицензия
├── README.md                       # Документация (этот файл)
├── pyproject.toml                  # Конфигурация пакета Python
├── requirements.txt                # Зависимости для pip
├── src/
│   └── swarm_mcp/
│       ├── __init__.py             # Экспорт публичного API (v2.0.0)
│       ├── __main__.py             # Точка входа: python -m swarm_mcp
│       ├── ask.py                  # Вопросы по проекту (ProjectQA)
│       ├── config.py               # MCPConfig с флагами оркестрации
│       ├── executor.py             # Безопасный запуск команд
│       ├── policy.py               # Политики безопасности из .swarm-policy.toml
│       ├── server.py               # MCP-сервер (5 инструментов)
│       └── status.py               # Анализ состояния проекта
└── tests/
    ├── __init__.py
    ├── test_ask.py                 # Тесты ProjectQA
    ├── test_executor.py            # Тесты CommandExecutor
    ├── test_policy.py              # Тесты SafetyPolicy
    ├── test_server.py              # Mock-тесты сервера
    └── test_status.py              # Тесты ProjectStatus
```

### Тесты

| Файл | Тестов | Описание |
|------|--------|----------|
| `test_server.py` | 21 | Создание сервера, 5 инструментов, вызовы, конфиг |
| `test_policy.py` | 14 | Загрузка политик, классификация команд |
| `test_executor.py` | 13 | Sanitizer, Executor, история, статистика |
| `test_status.py` | 7 | Анализ файлов, git, тесты, структура |
| `test_ask.py` | 10 | 9 категорий + общие вопросы |

---

## Docker

### Сборка образа

```bash
cd swarm-mcp
docker build -t swarm-mcp .
```

### Запуск контейнера

```bash
docker run -e DEEPSEEK_API_KEY=sk-your-key swarm-mcp
```

### Docker Compose

```yaml
version: "3.8"
services:
  swarm-mcp:
    build: .
    environment:
      - DEEPSEEK_API_KEY=${DEEPSEEK_API_KEY}
      - TEMPERATURE=0.1
      - MAX_ITERATIONS=3
```

---

## Лицензия

Проект распространяется под лицензией MIT. См. файл [LICENSE](LICENSE).
