"""Расширенная конфигурация для масштабируемой системы."""

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from swarm.config import SwarmConfig


@dataclass
class ScaleConfig:
    """Конфигурация масштабируемой системы.

    Поля:
        swarm_config: конфигурация базового роя (создаётся при первом обращении)
        cache_dir: директория для дискового кэша
        cache_size_gb: максимальный размер кэша в ГБ
        cache_ttl_hours: время жизни кэша в часах
        redis_url: URL Redis для распределённого кэша
        max_workers: максимальное количество параллельных воркеров
        batch_size: размер батча задач
        rpm_limit: лимит запросов в минуту к API
        enable_metrics: включить Prometheus метрики
        metrics_port: порт для HTTP-сервера метрик
        kafka_bootstrap_servers: адреса Kafka
        kafka_input_topic: входной топик задач
        kafka_output_topic: выходной топик результатов
        postgres_dsn: DSN для PostgreSQL
    """
    swarm_config: dict = field(default_factory=lambda: {})
    _swarm: Optional["SwarmConfig"] = None

    # Cache
    cache_dir: str = ".swarm_cache"
    cache_size_gb: int = 10
    cache_ttl_hours: int = 24
    redis_url: Optional[str] = None

    # Parallelism
    max_workers: int = 10
    batch_size: int = 20

    # Rate limiting
    rpm_limit: int = 500

    # Metrics
    enable_metrics: bool = True
    metrics_port: int = 8000

    # Queue (optional)
    kafka_bootstrap_servers: Optional[str] = None
    kafka_input_topic: str = "swarm-tasks"
    kafka_output_topic: str = "swarm-results"

    # Storage
    postgres_dsn: Optional[str] = None

    @property
    def swarm(self):
        """Ленивая загрузка SwarmConfig при первом обращении."""
        if self._swarm is None:
            from swarm.config import SwarmConfig
            if self.swarm_config:
                self._swarm = SwarmConfig(**self.swarm_config)
            else:
                self._swarm = SwarmConfig.from_env()
        return self._swarm

    @swarm.setter
    def swarm(self, value):
        """Позволяет установить SwarmConfig напрямую."""
        self._swarm = value

    @classmethod
    def from_env(cls, env_path: Optional[str] = None) -> "ScaleConfig":
        """Загружает конфигурацию из переменных окружения."""
        from dotenv import load_dotenv
        import os

        load_dotenv(dotenv_path=env_path)

        return cls(
            cache_dir=os.getenv("SCALE_CACHE_DIR", ".swarm_cache"),
            cache_size_gb=int(os.getenv("SCALE_CACHE_SIZE_GB", "10")),
            cache_ttl_hours=int(os.getenv("SCALE_CACHE_TTL_HOURS", "24")),
            redis_url=os.getenv("SCALE_REDIS_URL"),
            max_workers=int(os.getenv("SCALE_MAX_WORKERS", "10")),
            batch_size=int(os.getenv("SCALE_BATCH_SIZE", "20")),
            rpm_limit=int(os.getenv("SCALE_RPM_LIMIT", "500")),
            enable_metrics=os.getenv("SCALE_ENABLE_METRICS", "true").lower() == "true",
            metrics_port=int(os.getenv("SCALE_METRICS_PORT", "8000")),
            kafka_bootstrap_servers=os.getenv("SCALE_KAFKA_SERVERS"),
            kafka_input_topic=os.getenv("SCALE_KAFKA_INPUT_TOPIC", "swarm-tasks"),
            kafka_output_topic=os.getenv("SCALE_KAFKA_OUTPUT_TOPIC", "swarm-results"),
            postgres_dsn=os.getenv("SCALE_POSTGRES_DSN"),
        )
