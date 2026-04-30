FROM python:3.12-slim

WORKDIR /app

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements.txt и устанавливаем зависимости Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код
COPY src/ src/
COPY pyproject.toml README.md ./

# Устанавливаем пакет swarm-mcp в режиме разработки
RUN pip install --no-cache-dir -e .

# Создаём не-root пользователя
RUN useradd -m -u 1000 swarm && chown -R swarm:swarm /app
USER swarm

# Переменные окружения
ENV DEEPSEEK_API_KEY=""
ENV PYTHONUNBUFFERED=1

# Точка входа: запуск MCP-сервера через stdio
CMD ["python", "-m", "swarm_mcp"]
