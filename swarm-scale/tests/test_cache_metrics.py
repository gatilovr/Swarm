"""Тесты для cache-метрик Prometheus.

Все тесты используют before/after сравнения, т.к. Prometheus-метрики глобальны.
"""

import asyncio
import tempfile
import pytest
from swarm_scale.metrics import (
    SwarmMetrics,
    cache_hits_total,
    cache_misses_total,
    cache_hit_ratio,
)
from swarm_scale.cache import CacheManager
from swarm_scale.task import Task
from swarm_scale.config import ScaleConfig


class TestCacheMetricsCounters:
    """Тесты счётчиков cache hit/miss."""

    def test_cache_hit_counter(self):
        """cache_hits_total инкрементируется при hit."""
        before = cache_hits_total.labels(layer="l1")._value.get()
        SwarmMetrics.record_cache_hit("l1")
        after = cache_hits_total.labels(layer="l1")._value.get()
        assert after == before + 1

    def test_cache_miss_counter(self):
        """cache_misses_total инкрементируется при miss."""
        before = cache_misses_total.labels(layer="l1")._value.get()
        SwarmMetrics.record_cache_miss("l1")
        after = cache_misses_total.labels(layer="l1")._value.get()
        assert after == before + 1

    def test_cache_hit_multiple_layers(self):
        """Hit/miss считаются раздельно для разных слоёв."""
        l1_hits_before = cache_hits_total.labels(layer="l1")._value.get()
        l2_hits_before = cache_hits_total.labels(layer="l2")._value.get()

        SwarmMetrics.record_cache_hit("l1")
        SwarmMetrics.record_cache_hit("l2")
        SwarmMetrics.record_cache_hit("l1")

        assert cache_hits_total.labels(layer="l1")._value.get() == l1_hits_before + 2
        assert cache_hits_total.labels(layer="l2")._value.get() == l2_hits_before + 1

    def test_hit_ratio_updates(self):
        """cache_hit_ratio обновляется корректно."""
        l1_misses_before = cache_misses_total.labels(layer="l1")._value.get()
        l1_hits_before = cache_hits_total.labels(layer="l1")._value.get()

        # 3 hits, 1 miss
        for _ in range(3):
            SwarmMetrics.record_cache_hit("l1")
        SwarmMetrics.record_cache_miss("l1")

        hits = cache_hits_total.labels(layer="l1")._value.get()
        misses = cache_misses_total.labels(layer="l1")._value.get()

        hits_delta = hits - l1_hits_before
        misses_delta = misses - l1_misses_before
        total_delta = hits_delta + misses_delta
        ratio = hits_delta / total_delta if total_delta > 0 else 0.0

        SwarmMetrics.update_cache_hit_ratio("l1", ratio)

        # 3/4 = 0.75
        assert abs(ratio - 0.75) < 0.01

    def test_hit_ratio_zero_when_no_ops(self):
        """Hit ratio = 0.0, когда нет операций."""
        SwarmMetrics.update_cache_hit_ratio("l1", 0.0)
        assert cache_hit_ratio.labels(layer="l1")._value.get() == 0.0

    def test_cache_operations_counter(self):
        """cache_operations_total корректно считает операции."""
        from swarm_scale.metrics import cache_operations_total

        get_before = cache_operations_total.labels(operation="get")._value.get()
        set_before = cache_operations_total.labels(operation="set")._value.get()

        SwarmMetrics.record_cache_operation("get")
        SwarmMetrics.record_cache_operation("get")
        SwarmMetrics.record_cache_operation("set")

        assert cache_operations_total.labels(operation="get")._value.get() == get_before + 2
        assert cache_operations_total.labels(operation="set")._value.get() == set_before + 1

    def test_cache_latency_histogram(self):
        """cache_latency_seconds записывает latency."""
        from swarm_scale.metrics import cache_latency_seconds

        SwarmMetrics.record_cache_latency("get", "l1", 0.01)
        SwarmMetrics.record_cache_latency("get", "l1", 0.02)
        SwarmMetrics.record_cache_latency("set", "l2", 0.05)

        # Проверяем, что _sum увеличился (сумма всех наблюдений)
        sum_get_l1 = cache_latency_seconds.labels(operation="get", layer="l1")._sum.get()
        sum_set_l2 = cache_latency_seconds.labels(operation="set", layer="l2")._sum.get()

        assert sum_get_l1 >= 0.03  # 0.01 + 0.02
        assert sum_set_l2 >= 0.05


class TestCacheManagerWithMetrics:
    """Интеграционные тесты CacheManager + метрики."""

    @pytest.mark.asyncio
    async def test_cache_get_miss_records_metrics(self):
        """CacheManager записывает miss метрики при промахе."""
        tmpdir = tempfile.mkdtemp()
        try:
            config = ScaleConfig(cache_dir=tmpdir, cache_ttl_hours=24)
            config.redis_url = None  # No L2
            from swarm.config import SwarmConfig
            config.swarm = SwarmConfig()

            cache = CacheManager(config)

            task = Task(
                task_id="miss-test",
                content="some content that will miss",
                repository="org/repo",
                file_path="test.py",
            )

            l1_misses_before = cache_misses_total.labels(layer="l1")._value.get()

            # Miss
            result = await cache.get(task)
            assert result is None

            l1_misses_after = cache_misses_total.labels(layer="l1")._value.get()
            assert l1_misses_after == l1_misses_before + 1
        finally:
            if hasattr(cache.l1, '_cache') and hasattr(cache.l1._cache, 'close'):
                cache.l1._cache.close()
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_cache_set_and_get_hit_records_metrics(self):
        """CacheManager записывает hit метрики при попадании."""
        tmpdir = tempfile.mkdtemp()
        try:
            config = ScaleConfig(cache_dir=tmpdir, cache_ttl_hours=24)
            config.redis_url = None
            from swarm.config import SwarmConfig
            config.swarm = SwarmConfig()

            cache = CacheManager(config)

            task = Task(
                task_id="hit-test",
                content="test content for hit",
                repository="org/repo",
                file_path="test.py",
            )

            l1_hits_before = cache_hits_total.labels(layer="l1")._value.get()

            # Set + Get
            await cache.set(task, {"plan": "p", "code": "c"})
            result = await cache.get(task)

            assert result is not None
            l1_hits_after = cache_hits_total.labels(layer="l1")._value.get()
            assert l1_hits_after >= l1_hits_before + 1
        finally:
            if hasattr(cache.l1, '_cache') and hasattr(cache.l1._cache, 'close'):
                cache.l1._cache.close()
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_cache_operations_are_counted(self):
        """CacheManager записывает cache_operations_total."""
        from swarm_scale.metrics import cache_operations_total

        tmpdir = tempfile.mkdtemp()
        try:
            config = ScaleConfig(cache_dir=tmpdir, cache_ttl_hours=24)
            config.redis_url = None
            from swarm.config import SwarmConfig
            config.swarm = SwarmConfig()

            cache = CacheManager(config)

            task = Task(
                task_id="op-count-test",
                content="test",
                repository="org/repo",
                file_path="test.py",
            )

            get_before = cache_operations_total.labels(operation="get")._value.get()
            set_before = cache_operations_total.labels(operation="set")._value.get()

            # 1 set + 2 gets
            await cache.set(task, {"plan": "p", "code": "c"})
            await cache.get(task)
            await cache.get(task)

            get_after = cache_operations_total.labels(operation="get")._value.get()
            set_after = cache_operations_total.labels(operation="set")._value.get()

            assert get_after >= get_before + 2
            assert set_after >= set_before + 1
        finally:
            if hasattr(cache.l1, '_cache') and hasattr(cache.l1._cache, 'close'):
                cache.l1._cache.close()
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestModuleLevelFunctions:
    """Тесты module-level cache функций."""

    def test_module_level_cache_hit(self):
        """module-level record_cache_hit работает."""
        from swarm_scale.metrics import record_cache_hit, get_cache_hit_count

        before = get_cache_hit_count("l2")
        record_cache_hit("l2")
        after = get_cache_hit_count("l2")
        assert after == before + 1

    def test_module_level_cache_miss(self):
        """module-level record_cache_miss работает."""
        from swarm_scale.metrics import record_cache_miss, get_cache_miss_count

        before = get_cache_miss_count("l2")
        record_cache_miss("l2")
        after = get_cache_miss_count("l2")
        assert after == before + 1

    def test_module_level_cache_latency(self):
        """module-level record_cache_latency работает."""
        from swarm_scale.metrics import record_cache_latency, cache_latency_seconds

        sum_before = cache_latency_seconds.labels(operation="get", layer="l2")._sum.get()
        record_cache_latency("get", "l2", 0.1)
        sum_after = cache_latency_seconds.labels(operation="get", layer="l2")._sum.get()
        assert sum_after >= sum_before + 0.099  # с учётом float precision

    def test_module_level_update_hit_ratio(self):
        """module-level update_cache_hit_ratio работает."""
        from swarm_scale.metrics import update_cache_hit_ratio, cache_hit_ratio

        update_cache_hit_ratio("l2", 0.85)
        assert cache_hit_ratio.labels(layer="l2")._value.get() == 0.85
