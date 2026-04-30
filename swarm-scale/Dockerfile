# Используем официальный образ Python
FROM python:3.12-slim AS builder

WORKDIR /app

# Установка зависимостей
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- Финальный образ ---
FROM python:3.12-slim

WORKDIR /app

# Копируем зависимости из builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Копируем исходный код
COPY src/ ./src/
COPY pyproject.toml .
COPY README.md .

# Устанавливаем пакет
RUN pip install --no-cache-dir -e .

# Создаём непривилегированного пользователя
RUN groupadd -r swarm && useradd -r -g swarm swarm
USER swarm

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=60s --retries=3 \
    CMD python -c "import swarm_scale; print('OK')" || exit 1

# Точка входа — можно переопределить при запуске
ENTRYPOINT ["python", "-m", "swarm_scale"]
