"""Prometheus метрики для мониторинга системы.

Модуль предоставляет:
- Модульные функции для прямого использования (``record_task_completed`` и т.д.)
- Класс ``SwarmMetrics`` с тем же набором методов для объектного подхода
- Cache-specific метрики: hit/miss counters, latency histograms, size/hit_ratio gauges
"""

from prometheus_client import Counter, Histogram, Gauge, start_http_server
from typing import Optional


# --------------------------------------------------------------------------- #
# Module-level Prometheus метрики (registry)
# --------------------------------------------------------------------------- #

# Счётчики задач
tasks_total = Counter(
    "swarm_tasks_total",
    "Total number of processed tasks",
    ["status"],  # completed, failed, cached
)

tasks_duration = Histogram(
    "swarm_task_duration_seconds",
    "Task processing duration in seconds",
    buckets=[1, 5, 10, 30, 60, 120, 300, 600],
)

# Счётчики токенов и стоимости
tokens_total = Counter(
    "swarm_tokens_total",
    "Total tokens consumed",
    ["model"],
)

cost_total = Counter(
    "swarm_cost_usd_total",
    "Total cost in USD",
)

# Текущие метрики
active_workers = Gauge(
    "swarm_active_workers",
    "Number of currently active workers",
)

queue_depth = Gauge(
    "swarm_queue_depth",
    "Current queue depth",
)

cache_size = Gauge(
    "swarm_cache_size_bytes",
    "Current cache size in bytes",
)

rpm_current = Gauge(
    "swarm_rpm_current",
    "Current RPM limit",
)

# ===== Cache-специфичные метрики =====

cache_hits_total = Counter(
    "swarm_cache_hits_total",
    "Total cache hits by layer",
    ["layer"],  # l1, l2
)

cache_misses_total = Counter(
    "swarm_cache_misses_total",
    "Total cache misses by layer",
    ["layer"],  # l1, l2
)

cache_operations_total = Counter(
    "swarm_cache_operations_total",
    "Total cache operations by type",
    ["operation"],  # get, set, delete
)

cache_latency_seconds = Histogram(
    "swarm_cache_latency_seconds",
    "Cache operation latency in seconds",
    ["operation", "layer"],  # operation=get|set, layer=l1|l2
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)

cache_hit_ratio = Gauge(
    "swarm_cache_hit_ratio",
    "Current cache hit ratio (0.0-1.0)",
    ["layer"],  # l1, l2
)


class SwarmMetrics:
    """Обёртка над модульными Prometheus-метриками.

    Упрощает интеграцию в OOP-код и позволяет передавать
    экземпляр как зависимость.

    Регистрируемые метрики:
        - ``swarm_tasks_total`` — счётчик задач по статусу
        - ``swarm_task_duration_seconds`` — гистограмма длительности
        - ``swarm_tokens_total`` — счётчик токенов по модели
        - ``swarm_cost_usd_total`` — счётчик стоимости в USD
        - ``swarm_active_workers`` — текущее число активных воркеров
        - ``swarm_queue_depth`` — текущая глубина очереди
        - ``swarm_cache_size_bytes`` — размер кэша в байтах
        - ``swarm_rpm_current`` — текущий RPM-лимит
        - ``swarm_cache_hits_total`` — cache hits по слоям
        - ``swarm_cache_misses_total`` — cache misses по слоям
        - ``swarm_cache_operations_total`` — операции кэша по типу
        - ``swarm_cache_latency_seconds`` — гистограмма latency кэша
        - ``swarm_cache_hit_ratio`` — hit ratio по слоям
    """

    def __init__(self) -> None:
        """Инициализирует SwarmMetrics.

        Все метрики уже зарегистрированы на уровне модуля,
        поэтому экземпляр просто ссылается на глобальный registry.
        """
        pass

    @staticmethod
    def record_task(status: str, duration_sec: Optional[float] = None) -> None:
        """Записывает метрику выполнения задачи.

        Увеличивает счётчик ``swarm_tasks_total`` с лейблом ``status``.
        Если передан ``duration_sec``, также записывает длительность
        в гистограмму ``swarm_task_duration_seconds``.

        Args:
            status: статус задачи (``completed``, ``failed``, ``cached``).
            duration_sec: длительность выполнения в секундах (опционально).
        """
        tasks_total.labels(status=status).inc()
        if duration_sec is not None:
            tasks_duration.observe(duration_sec)

    @staticmethod
    def record_tokens(model: str, count: int) -> None:
        """Логирует потребление токенов.

        Увеличивает счётчик ``swarm_tokens_total`` с лейблом ``model``.

        Args:
            model: имя модели (например, ``deepseek-chat``).
            count: количество потраченных токенов.
        """
        tokens_total.labels(model=model).inc(count)

    @staticmethod
    def record_cost(usd: float) -> None:
        """Записывает стоимость выполнения в USD.

        Увеличивает счётчик ``swarm_cost_usd_total``.

        Args:
            usd: стоимость в долларах США.
        """
        cost_total.inc(usd)

    # ===== Cache-методы =====

    @staticmethod
    def record_cache_hit(layer: str = "l1") -> None:
        """Записывает cache hit для указанного слоя.

        Args:
            layer: уровень кэша (``l1``, ``l2``).
        """
        cache_hits_total.labels(layer=layer).inc()

    @staticmethod
    def record_cache_miss(layer: str = "l1") -> None:
        """Записывает cache miss для указанного слоя.

        Args:
            layer: уровень кэша (``l1``, ``l2``).
        """
        cache_misses_total.labels(layer=layer).inc()

    @staticmethod
    def record_cache_latency(operation: str, layer: str, latency: float) -> None:
        """Записывает latency операции кэша.

        Args:
            operation: тип операции (``get``, ``set``).
            layer: уровень кэша (``l1``, ``l2``).
            latency: время выполнения в секундах.
        """
        cache_latency_seconds.labels(operation=operation, layer=layer).observe(latency)

    @staticmethod
    def record_cache_operation(operation: str) -> None:
        """Записывает операцию кэша (get/set/delete).

        Args:
            operation: тип операции (``get``, ``set``, ``delete``).
        """
        cache_operations_total.labels(operation=operation).inc()

    @staticmethod
    def update_cache_hit_ratio(layer: str, ratio: float) -> None:
        """Обновляет hit ratio для слоя (0.0-1.0).

        Args:
            layer: уровень кэша (``l1``, ``l2``).
            ratio: hit ratio от 0.0 до 1.0.
        """
        cache_hit_ratio.labels(layer=layer).set(ratio)

    @staticmethod
    def get_cache_hit_count(layer: str) -> int:
        """Возвращает количество cache hits для слоя.

        Args:
            layer: уровень кэша (``l1``, ``l2``).

        Returns:
            Количество cache hits.
        """
        return cache_hits_total.labels(layer=layer)._value.get()

    @staticmethod
    def get_cache_miss_count(layer: str) -> int:
        """Возвращает количество cache misses для слоя.

        Args:
            layer: уровень кэша (``l1``, ``l2``).

        Returns:
            Количество cache misses.
        """
        return cache_misses_total.labels(layer=layer)._value.get()


# --------------------------------------------------------------------------- #
# Module-level функции (backward compatibility)
# --------------------------------------------------------------------------- #


def start_metrics_server(port: int = 8000) -> None:
    """Запускает HTTP-сервер для Prometheus метрик.

    Args:
        port: порт для HTTP-сервера
    """
    start_http_server(port)


def record_task_completed(duration_sec: float) -> None:
    """Записывает метрики успешно выполненной задачи.

    Args:
        duration_sec: длительность выполнения в секундах
    """
    tasks_total.labels(status="completed").inc()
    tasks_duration.observe(duration_sec)


def record_task_failed() -> None:
    """Записывает метрику упавшей задачи."""
    tasks_total.labels(status="failed").inc()


def record_task_cached() -> None:
    """Записывает метрику задачи из кэша."""
    tasks_total.labels(status="cached").inc()


def record_tokens(model: str, count: int) -> None:
    """Записывает потребление токенов.

    Args:
        model: имя модели
        count: количество токенов
    """
    tokens_total.labels(model=model).inc(count)


def record_cost(usd: float) -> None:
    """Записывает стоимость выполнения.

    Args:
        usd: стоимость в долларах
    """
    cost_total.inc(usd)


# ===== Cache module-level функции =====


def record_cache_hit(layer: str = "l1") -> None:
    """Записывает cache hit для указанного слоя.

    Args:
        layer: уровень кэша (``l1``, ``l2``).
    """
    cache_hits_total.labels(layer=layer).inc()


def record_cache_miss(layer: str = "l1") -> None:
    """Записывает cache miss для указанного слоя.

    Args:
        layer: уровень кэша (``l1``, ``l2``).
    """
    cache_misses_total.labels(layer=layer).inc()


def record_cache_latency(operation: str, layer: str, latency: float) -> None:
    """Записывает latency операции кэша.

    Args:
        operation: тип операции (``get``, ``set``).
        layer: уровень кэша (``l1``, ``l2``).
        latency: время выполнения в секундах.
    """
    cache_latency_seconds.labels(operation=operation, layer=layer).observe(latency)


def record_cache_operation(operation: str) -> None:
    """Записывает операцию кэша (get/set/delete).

    Args:
        operation: тип операции (``get``, ``set``, ``delete``).
    """
    cache_operations_total.labels(operation=operation).inc()


def update_cache_hit_ratio(layer: str, ratio: float) -> None:
    """Обновляет hit ratio для слоя (0.0-1.0).

    Args:
        layer: уровень кэша (``l1``, ``l2``).
        ratio: hit ratio от 0.0 до 1.0.
    """
    cache_hit_ratio.labels(layer=layer).set(ratio)


def get_cache_hit_count(layer: str) -> int:
    """Возвращает количество cache hits для слоя.

    Args:
        layer: уровень кэша (``l1``, ``l2``).

    Returns:
        Количество cache hits.
    """
    return cache_hits_total.labels(layer=layer)._value.get()


def get_cache_miss_count(layer: str) -> int:
    """Возвращает количество cache misses для слоя.

    Args:
        layer: уровень кэша (``l1``, ``l2``).

    Returns:
        Количество cache misses.
    """
    return cache_misses_total.labels(layer=layer)._value.get()
