"""Тесты для конфигурации масштабирования (ScaleConfig)."""

import pytest

from swarm_scale.config import ScaleConfig


class TestScaleConfigDefaults:
    """Тесты значений по умолчанию."""

    def test_default_cache_dir(self):
        """cache_dir по умолчанию .swarm_cache."""
        config = ScaleConfig()
        assert config.cache_dir == ".swarm_cache"

    def test_default_cache_size(self):
        """cache_size_gb по умолчанию 10."""
        config = ScaleConfig()
        assert config.cache_size_gb == 10

    def test_default_cache_ttl(self):
        """cache_ttl_hours по умолчанию 24."""
        config = ScaleConfig()
        assert config.cache_ttl_hours == 24

    def test_default_max_workers(self):
        """max_workers по умолчанию 10."""
        config = ScaleConfig()
        assert config.max_workers == 10

    def test_default_batch_size(self):
        """batch_size по умолчанию 20."""
        config = ScaleConfig()
        assert config.batch_size == 20

    def test_default_rpm_limit(self):
        """rpm_limit по умолчанию 500."""
        config = ScaleConfig()
        assert config.rpm_limit == 500

    def test_default_metrics_enabled(self):
        """enable_metrics по умолчанию True."""
        config = ScaleConfig()
        assert config.enable_metrics is True

    def test_default_metrics_port(self):
        """metrics_port по умолчанию 8000."""
        config = ScaleConfig()
        assert config.metrics_port == 8000

    def test_default_redis_url(self):
        """redis_url по умолчанию None."""
        config = ScaleConfig()
        assert config.redis_url is None

    def test_default_kafka_servers(self):
        """kafka_bootstrap_servers по умолчанию None."""
        config = ScaleConfig()
        assert config.kafka_bootstrap_servers is None

    def test_default_postgres_dsn(self):
        """postgres_dsn по умолчанию None."""
        config = ScaleConfig()
        assert config.postgres_dsn is None

    def test_default_optional_fields_none(self):
        """Опциональные поля без значения — None."""
        config = ScaleConfig()
        assert config.redis_url is None
        assert config.kafka_bootstrap_servers is None
        assert config.postgres_dsn is None


class TestScaleConfigCustom:
    """Тесты с кастомными значениями."""

    def test_custom_cache_settings(self):
        """Переопределение cache-параметров."""
        config = ScaleConfig(
            cache_dir="/custom/cache",
            cache_size_gb=50,
            cache_ttl_hours=48,
        )
        assert config.cache_dir == "/custom/cache"
        assert config.cache_size_gb == 50
        assert config.cache_ttl_hours == 48

    def test_custom_parallelism(self):
        """Переопределение параметров параллелизма."""
        config = ScaleConfig(
            max_workers=20,
            batch_size=50,
        )
        assert config.max_workers == 20
        assert config.batch_size == 50

    def test_custom_rpm(self):
        """Переопределение RPM."""
        config = ScaleConfig(rpm_limit=1000)
        assert config.rpm_limit == 1000

    def test_custom_metrics_disabled(self):
        """Отключение метрик."""
        config = ScaleConfig(enable_metrics=False)
        assert config.enable_metrics is False

    def test_custom_metrics_port(self):
        """Кастомный порт метрик."""
        config = ScaleConfig(metrics_port=9090)
        assert config.metrics_port == 9090

    def test_custom_kafka(self):
        """Настройки Kafka."""
        config = ScaleConfig(
            kafka_bootstrap_servers="broker1:9092,broker2:9092",
            kafka_input_topic="custom-input",
            kafka_output_topic="custom-output",
        )
        assert "broker1:9092" in config.kafka_bootstrap_servers
        assert config.kafka_input_topic == "custom-input"
        assert config.kafka_output_topic == "custom-output"

    def test_custom_redis(self):
        """Настройки Redis."""
        config = ScaleConfig(redis_url="redis://localhost:6379/0")
        assert config.redis_url == "redis://localhost:6379/0"

    def test_custom_postgres(self):
        """Настройки PostgreSQL."""
        config = ScaleConfig(
            postgres_dsn="postgresql://user:pass@localhost:5432/swarm"
        )
        assert "postgresql://" in config.postgres_dsn
        assert "swarm" in config.postgres_dsn

    def test_all_custom_values(self):
        """Все поля переопределены."""
        config = ScaleConfig(
            cache_dir="/cache",
            cache_size_gb=100,
            cache_ttl_hours=1,
            redis_url="redis://r:6379",
            max_workers=50,
            batch_size=100,
            rpm_limit=2000,
            enable_metrics=False,
            metrics_port=9999,
            kafka_bootstrap_servers="kafka:9092",
            kafka_input_topic="in",
            kafka_output_topic="out",
            postgres_dsn="pg://localhost/swarm",
        )
        assert config.cache_dir == "/cache"
        assert config.max_workers == 50
        assert config.rpm_limit == 2000
        assert config.enable_metrics is False
        assert config.metrics_port == 9999


class TestScaleConfigFromEnv:
    """Тесты загрузки из переменных окружения."""

    def test_from_env_empty(self, monkeypatch):
        """Без переменных — значения по умолчанию."""
        config = ScaleConfig.from_env()
        assert config.cache_dir == ".swarm_cache"
        assert config.max_workers == 10

    def test_from_env_custom_values(self, monkeypatch):
        """С переменными окружения."""
        monkeypatch.setenv("SCALE_CACHE_DIR", "/env/cache")
        monkeypatch.setenv("SCALE_MAX_WORKERS", "25")
        monkeypatch.setenv("SCALE_RPM_LIMIT", "750")
        monkeypatch.setenv("SCALE_ENABLE_METRICS", "false")
        monkeypatch.setenv("SCALE_METRICS_PORT", "8888")
        monkeypatch.setenv("SCALE_REDIS_URL", "redis://env:6379")
        monkeypatch.setenv("SCALE_KAFKA_SERVERS", "env-kafka:9092")

        config = ScaleConfig.from_env()
        assert config.cache_dir == "/env/cache"
        assert config.max_workers == 25
        assert config.rpm_limit == 750
        assert config.enable_metrics is False
        assert config.metrics_port == 8888
        assert config.redis_url == "redis://env:6379"
        assert config.kafka_bootstrap_servers == "env-kafka:9092"

    def test_from_env_boolean_parsing(self, monkeypatch):
        """Парсинг булевых значений."""
        monkeypatch.setenv("SCALE_ENABLE_METRICS", "false")
        config = ScaleConfig.from_env()
        assert config.enable_metrics is False

        monkeypatch.setenv("SCALE_ENABLE_METRICS", "true")
        config = ScaleConfig.from_env()
        assert config.enable_metrics is True

    def test_from_env_partial(self, monkeypatch):
        """Частичное переопределение — остальное по умолчанию."""
        monkeypatch.setenv("SCALE_MAX_WORKERS", "5")

        config = ScaleConfig.from_env()
        assert config.max_workers == 5
        assert config.cache_dir == ".swarm_cache"  # default
        assert config.rpm_limit == 500  # default


class TestScaleConfigSwarmIntegration:
    """Тесты интеграции с SwarmConfig."""

    def test_swarm_property_lazy_loading(self):
        """SwarmConfig создаётся лениво (только при обращении к .swarm)."""
        config = ScaleConfig()
        # ._swarm должен быть None до первого обращения
        assert config._swarm is None

        # Обращаемся к .swarm
        swarm = config.swarm
        assert swarm is not None
        # _swarm теперь заполнен
        assert config._swarm is not None

    def test_swarm_property_caches(self):
        """Повторное обращение к .swarm возвращает тот же объект."""
        config = ScaleConfig()
        swarm1 = config.swarm
        swarm2 = config.swarm
        assert swarm1 is swarm2

    def test_swarm_with_dict(self):
        """swarm_config из словаря."""
        config = ScaleConfig(
            swarm_config={
                "deepseek_api_key": "test-key",
                "max_iterations": 5,
            }
        )
        swarm = config.swarm
        assert swarm.deepseek_api_key == "test-key"
        assert swarm.max_iterations == 5

    def test_swarm_setter(self):
        """Прямая установка SwarmConfig через setter."""
        from swarm.config import SwarmConfig

        custom = SwarmConfig(deepseek_api_key="direct-key")
        config = ScaleConfig()
        config.swarm = custom

        assert config.swarm.deepseek_api_key == "direct-key"
        assert config._swarm is custom

    def test_swarm_from_env_fallback(self, monkeypatch):
        """Если swarm_config пуст — from_env()."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "env-swarm-key")
        config = ScaleConfig()  # swarm_config={}
        swarm = config.swarm
        assert swarm.deepseek_api_key == "env-swarm-key"
