# Swarm MCP Server

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Swarm MCP Server** — это MCP-сервер (Model Context Protocol) для роя AI-агентов, который предоставляет инструмент `run_swarm`. Сервер позволяет Roo Code и другим MCP-клиентам запускать команду из трёх AI-агентов, работающих в цикле:

1. **🏗️ Архитектор** — анализирует техническое задание и создаёт план
2. **💻 Кодер** — пишет код по утверждённому плану
3. **🔍 Ревьюер** — проверяет код (APPROVED/REJECTED)

При отклонении код отправляется на доработку (до 3 итераций).

---

## Содержание

- [Установка](#установка)
- [Быстрый старт](#быстрый-старт)
- [Конфигурация](#конфигурация)
- [API](#api)
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
# Клонируйте репозиторий
git clone <your-repo-url>
cd swarm-mcp

# Установите в режиме разработки
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

Добавьте MCP-сервер в конфигурацию Roo Code:

```json
{
  "mcpServers": {
    "code-swarm": {
      "command": "python",
      "args": ["-m", "swarm_mcp"],
      "env": {
        "DEEPSEEK_API_KEY": "sk-your-api-key"
      }
    }
  }
}
```

После подключения инструмент `run_swarm` будет доступен в Roo Code.

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
| `ARCHITECT_MODEL` | Модель для архитектора | `deepseek-chat` |
| `CODER_MODEL` | Модель для кодера | `deepseek-chat` |
| `REVIEWER_MODEL` | Модель для ревьюера | `deepseek-chat` |
| `BASE_URL` | Базовый URL API DeepSeek | `https://api.deepseek.com/v1` |
| `TEMPERATURE` | Температура модели (0.0–1.0) | `0.1` |
| `MAX_ITERATIONS` | Максимум циклов кодер→ревьюер | `3` |

### Пример `.env`

```env
DEEPSEEK_API_KEY=sk-your-key-here
ARCHITECT_MODEL=deepseek-chat
CODER_MODEL=deepseek-chat
REVIEWER_MODEL=deepseek-chat
BASE_URL=https://api.deepseek.com/v1
TEMPERATURE=0.1
MAX_ITERATIONS=3
```

---

## API

### Инструмент `run_swarm`

Запускает рой AI-агентов для выполнения задачи.

#### Параметры

| Параметр | Тип | Обязательный | Описание |
|---------|-----|-------------|----------|
| `task` | `string` | ✅ | Детальное техническое задание на разработку |

#### Формат ответа

Успешный ответ содержит markdown-разделы:

```markdown
## 🏗️ План архитектора
(план, сгенерированный архитектором)

---

## 💻 Итоговый код
```python
(код, сгенерированный кодером)
```

---

## 🔍 Результат ревью
(результат проверки ревьюером: APPROVED/REJECTED)
```

#### Пример ответа (сокращённый)

```markdown
## 🏗️ План архитектора

1. Создать функцию quicksort с рекурсивным подходом
2. Выбрать опорный элемент (pivot) — средний элемент массива
3. Разделить массив на элементы меньше и больше pivot
4. Рекурсивно отсортировать подмассивы
5. Объединить результаты

---

## 💻 Итоговый код

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

---

## 🔍 Результат ревью

APPROVED
```

#### Ошибки

Сервер возвращает сообщения вида:

- `ERROR: DEEPSEEK_API_KEY not configured.` — отсутствует API-ключ
- `ERROR: Parameter 'task' is required.` — не передан параметр `task`
- `ERROR: <текст ошибки>` — ошибка при выполнении (ошибка API, таймаут и т.д.)

---

## Архитектура

```
┌─────────────────────────────────────────────────────────┐
│                   MCP Client (Roo Code)                  │
└──────────────────────┬──────────────────────────────────┘
                       │ JSON-RPC (stdio)
┌──────────────────────▼──────────────────────────────────┐
│                   swarm-mcp (MCP Server)                 │
│                                                          │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐           │
│  │  Server   │───▷│ call_tool│───▷│ run_swarm│           │
│  │ (MCP)     │    │ handler  │    │ handler  │           │
│  └──────────┘    └──────────┘    └─────┬────┘           │
│                                         │                │
│  ┌──────────────────────────────────────▼──────────────┐ │
│  │                 SwarmRunner                          │ │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐        │ │
│  │  │Architect │──▷│  Coder   │──▷│ Reviewer │──▷      │ │
│  │  │ (plan)   │   │ (code)   │   │(review)  │  loop   │ │
│  │  └──────────┘   └──────────┘   └──────────┘        │ │
│  └─────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

### Компоненты

1. **MCP Server Layer** (`server.py`) — обрабатывает MCP-запросы через `list_tools` и `call_tool`, выполняет валидацию, управляет ошибками
2. **Config Layer** (`config.py`) — загружает и предоставляет конфигурацию
3. **Swarm Layer** (`swarm` package) — ядро роя: граф LangGraph с тремя агентами

### Поток выполнения

1. Клиент вызывает `run_swarm` с параметром `task`
2. Сервер проверяет API-ключ и валидирует входные данные
3. Создаётся `SwarmRunner` с загруженной конфигурацией
4. Запускается `runner.stream(task)` — пошаговое выполнение графа
5. На каждом шаге отправляется прогресс-уведомление (опционально)
6. После завершения формируется структурированный ответ
7. Ответ возвращается клиенту

---

## Разработка

### Установка для разработки

```bash
# Из корня swarm-mcp/
pip install -e .
pip install pytest pytest-asyncio
```

### Запуск тестов

```bash
# Из корня swarm-mcp/
python -m pytest tests/test_server.py -v
```

### Структура проекта

```
swarm-mcp/
├── Dockerfile                  # Docker-образ
├── LICENSE                     # MIT лицензия
├── README.md                   # Документация (этот файл)
├── pyproject.toml              # Конфигурация пакета Python
├── requirements.txt            # Зависимости для pip
├── src/
│   └── swarm_mcp/
│       ├── __init__.py         # Экспорт публичного API
│       ├── __main__.py         # Точка входа: python -m swarm_mcp
│       ├── config.py           # Конфигурация MCP-сервера
│       └── server.py           # MCP-сервер (инструмент run_swarm)
└── tests/
    ├── __init__.py
    └── test_server.py          # Mock-тесты MCP-сервера
```

### Написание тестов

Тесты используют `unittest.mock` для изоляции:

```python
@pytest.mark.asyncio
async def test_successful_run():
    result = await server.call_tool("run_swarm", {"task": "test"})
    assert "План архитектора" in result[0].text
```

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

### Docker Compose (пример)

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
