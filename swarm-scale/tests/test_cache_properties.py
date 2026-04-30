"""Property-based тесты для модуля кэширования.

Инварианты:
- Roundtrip: set(X) → get(X) == X для любых данных
- Cache miss: разные ключи не пересекаются
- Множественные записи не теряются
"""
import tempfile
import shutil
import pytest
from hypothesis import given, settings, strategies as st
from swarm_scale.cache import DiskCache, CacheManager
from swarm_scale.task import Task
from swarm_scale.config import ScaleConfig


# Стратегии для генерации данных
text_strategy = st.text(
    min_size=1, max_size=100,
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789 _-",
)
result_strategy = st.fixed_dictionaries({
    "plan": st.text(max_size=50),
    "code": st.text(max_size=50),
    "review_result": st.text(max_size=50),
    "approved": st.booleans(),
    "iterations": st.integers(min_value=0, max_value=10),
})
ttl_hours_strategy = st.integers(min_value=1, max_value=720)  # 1 hour to 30 days


class TestDiskCacheProperties:
    """Property-based тесты для DiskCache (L1)."""

    @settings(deadline=1000)
    @given(
        key=text_strategy,
        value=result_strategy,
        ttl_hours=ttl_hours_strategy,
    )
    @pytest.mark.asyncio
    async def test_disk_cache_roundtrip(self, key, value, ttl_hours):
        """DiskCache: set(key, value) → get(key) == value для любых данных."""
        tmpdir = tempfile.mkdtemp()
        try:
            cache = DiskCache(directory=tmpdir, ttl_hours=ttl_hours, max_size_gb=1)
            await cache.set(key, value)
            result = await cache.get(key)
            assert result is not None
            assert result == value
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @settings(deadline=1000)
    @given(
        key1=text_strategy,
        key2=text_strategy,
        value=result_strategy,
        ttl_hours=ttl_hours_strategy,
    )
    @pytest.mark.asyncio
    async def test_disk_cache_miss_on_different_key(self, key1, key2, value, ttl_hours):
        """DiskCache: set(X) → get(Y) == None если X != Y."""
        # Гарантируем разные ключи
        if key1 == key2:
            key2 = key2 + "_different"
        tmpdir = tempfile.mkdtemp()
        try:
            cache = DiskCache(directory=tmpdir, ttl_hours=ttl_hours, max_size_gb=1)
            await cache.set(key1, value)
            result = await cache.get(key2)
            assert result is None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @settings(deadline=1000)
    @given(
        keys=st.lists(text_strategy, min_size=2, max_size=10),
        value=result_strategy,
        ttl_hours=ttl_hours_strategy,
    )
    @pytest.mark.asyncio
    async def test_disk_cache_multiple_keys(self, keys, value, ttl_hours):
        """DiskCache: множество ключей с одинаковым значением не пересекаются."""
        # Дедуплицируем ключи
        unique_keys = list(dict.fromkeys(keys))
        if len(unique_keys) < 2:
            return  # Нужно минимум 2 разных ключа
        tmpdir = tempfile.mkdtemp()
        try:
            cache = DiskCache(directory=tmpdir, ttl_hours=ttl_hours, max_size_gb=1)
            for k in unique_keys:
                await cache.set(k, value)
            for k in unique_keys:
                result = await cache.get(k)
                assert result is not None
                assert result == value
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @settings(deadline=1000)
    @given(
        ttl_hours=ttl_hours_strategy,
    )
    @pytest.mark.asyncio
    async def test_disk_cache_empty_initially(self, ttl_hours):
        """DiskCache: новый кэш пуст."""
        tmpdir = tempfile.mkdtemp()
        try:
            cache = DiskCache(directory=tmpdir, ttl_hours=ttl_hours, max_size_gb=1)
            result = await cache.get("any_key")
            assert result is None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


class TestCacheManagerProperties:
    """Property-based тесты для CacheManager (L1+L2)."""

    @settings(deadline=1000)
    @given(
        content=text_strategy,
        repo=text_strategy,
        file_path=text_strategy,
        result_data=result_strategy,
        ttl_hours=ttl_hours_strategy,
    )
    @pytest.mark.asyncio
    async def test_cache_manager_roundtrip(self, content, repo, file_path, result_data, ttl_hours):
        """CacheManager: set(task, result) → get(task) == result."""
        tmpdir = tempfile.mkdtemp()
        try:
            config = ScaleConfig(
                cache_dir=tmpdir,
                cache_ttl_hours=ttl_hours,
            )
            config.swarm = None  # Отключаем SwarmConfig для тестов
            manager = CacheManager(config)

            task = Task(
                task_id=repo + "_" + file_path,
                content=content or "default_content",
                repository=repo or "default_repo",
                file_path=file_path or "default_path",
            )

            await manager.set(task, result_data)
            result = await manager.get(task)

            assert result is not None
            # Проверяем, что вернулись те же данные
            for key in result_data:
                assert result[key] == result_data[key]
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @settings(deadline=1000)
    @given(
        content=text_strategy,
        repo=text_strategy,
        file_path=text_strategy,
        ttl_hours=ttl_hours_strategy,
    )
    @pytest.mark.asyncio
    async def test_cache_manager_miss_initially(self, content, repo, file_path, ttl_hours):
        """CacheManager: get() для незаписанной задачи → None."""
        tmpdir = tempfile.mkdtemp()
        try:
            config = ScaleConfig(
                cache_dir=tmpdir,
                cache_ttl_hours=ttl_hours,
            )
            config.swarm = None
            manager = CacheManager(config)

            task = Task(
                task_id="test_id",
                content=content or "default_content",
                repository=repo or "default_repo",
                file_path=file_path or "default_path",
            )

            result = await manager.get(task)
            assert result is None
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    @settings(deadline=1000)
    @given(
        content=text_strategy,
        ttl_hours=ttl_hours_strategy,
    )
    @pytest.mark.asyncio
    async def test_cache_stats_consistency(self, content, ttl_hours):
        """CacheManager: статистика консистентна (miss + hit = total)."""
        tmpdir = tempfile.mkdtemp()
        try:
            config = ScaleConfig(
                cache_dir=tmpdir,
                cache_ttl_hours=ttl_hours,
            )
            config.swarm = None
            manager = CacheManager(config)

            task = Task(
                task_id="test_id",
                content=content or "default_content",
                repository="repo",
                file_path="path",
            )
            result_data = {"plan": "test", "code": "test", "approved": True}

            # Miss
            miss_result = await manager.get(task)
            assert miss_result is None

            # Set + Hit
            await manager.set(task, result_data)
            hit_result = await manager.get(task)
            assert hit_result is not None

            stats = manager.stats()
            assert stats["miss"] == 1
            assert stats["l1"] >= 1
            assert stats["hit_rate_pct"] > 0
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
