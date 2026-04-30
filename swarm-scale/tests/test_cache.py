"""Тесты для модуля кэширования."""

import asyncio
import tempfile
import pytest
from swarm_scale.cache import DiskCache, CacheManager
from swarm_scale.task import Task
from swarm_scale.config import ScaleConfig


class TestDiskCache:
    """Тесты DiskCache (L1)."""

    def test_cache_set_get(self):
        """Запись и чтение из кэша."""
        cache = DiskCache(directory=".test_cache", ttl_hours=24, max_size_gb=1)
        key = "test:key123"
        value = {"plan": "test plan", "code": "print('hello')"}

        cache.set(key, value)
        result = cache.get(key)

        assert result == value
        assert result["plan"] == "test plan"

    def test_cache_miss(self):
        """Возврат None для отсутствующего ключа."""
        cache = DiskCache(directory=".test_cache", ttl_hours=24, max_size_gb=1)
        result = cache.get("nonexistent:key")
        assert result is None

    def test_cache_key_uniqueness(self):
        """Разные задачи = разные ключи."""
        cache = DiskCache(directory=".test_cache", ttl_hours=24, max_size_gb=1)

        task1 = Task(
            task_id="1",
            content="Напиши тест",
            repository="org/repo1",
            file_path="test.py",
        )
        task2 = Task(
            task_id="2",
            content="Напиши функцию",
            repository="org/repo2",
            file_path="main.py",
        )

        key1 = cache.make_key(task1)
        key2 = cache.make_key(task2)

        assert key1 != key2

    def test_cache_stats(self):
        """Проверка статистики кэша."""
        tmpdir = tempfile.mkdtemp()
        try:
            config = ScaleConfig()
            config.cache_dir = tmpdir
            from swarm.config import SwarmConfig
            config.swarm = SwarmConfig()
            manager = CacheManager(config)

            task = Task(
                task_id="1",
                content="test content",
                repository="org/repo",
                file_path="test.py",
            )

            # Miss
            result = asyncio.run(manager.get(task))
            assert result is None
            assert manager.hits["miss"] == 1

            # Set and Get (L1 hit)
            asyncio.run(manager.set(task, {"plan": "p", "code": "c"}))
            result = asyncio.run(manager.get(task))
            assert result is not None
            assert manager.hits["l1"] == 1

            # Проверка stats
            stats = manager.stats()
            assert stats["l1"] == 1
            assert stats["miss"] == 1
            assert stats["hit_rate_pct"] > 0
        finally:
            # Явно закрываем diskcache перед удалением (иначе PermissionError на Windows)
            if hasattr(manager.l1, '_cache') and hasattr(manager.l1._cache, 'close'):
                manager.l1._cache.close()
            import shutil
            shutil.rmtree(tmpdir, ignore_errors=True)
