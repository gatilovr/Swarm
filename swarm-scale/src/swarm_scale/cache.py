"""Многоуровневое кэширование результатов роя.

L1: diskcache — локальный кэш на диске (быстрый, per-worker)
L2: Redis — распределённый кэш (shared между воркерами)
L3: S3/PostgreSQL — долгосрочное хранение

Все операции кэша отслеживаются через OpenTelemetry tracing и Prometheus метрики.
"""

import asyncio
import hashlib
import json
import logging
import time
from typing import Optional, Any
from datetime import datetime, timedelta

from swarm.tracing import get_tracer
from swarm_scale.metrics import SwarmMetrics

logger = logging.getLogger(__name__)


class CacheLevel:
    """Базовый уровень кэша с TTL и размером."""

    def __init__(self, name: str, ttl_hours: int = 24, max_size_gb: int = 10):
        self.name = name
        self.ttl = timedelta(hours=ttl_hours)
        self.max_size_gb = max_size_gb

    def make_key(self, task: "Task", profile_id: Optional[str] = None) -> str:
        """Создаёт хеш-ключ на основе задачи + контекста."""
        content = json.dumps({
            "task": task.content,
            "repository": task.repository,
            "file_path": task.file_path,
            "profile_id": profile_id,
        }, sort_keys=True)
        return f"swarm:{hashlib.sha256(content.encode()).hexdigest()}"


class DiskCache(CacheLevel):
    """L1: Локальный дисковый кэш на основе diskcache."""

    def __init__(self, directory: str = ".swarm_cache", ttl_hours: int = 24, max_size_gb: int = 10):
        super().__init__("disk", ttl_hours, max_size_gb)
        try:
            from diskcache import Cache
            self._cache = Cache(
                directory=directory,
                size_limit=max_size_gb * 1024**3,
                eviction_policy="least-recently-used",
            )
            self._in_memory = False
        except ImportError:
            logger.warning("diskcache not installed, using in-memory fallback")
            self._cache = {}
            self._in_memory = True

    async def get(self, key: str) -> Optional[dict]:
        """Асинхронно получает результат из кэша (I/O в thread pool)."""
        try:
            if self._in_memory:
                return self._cache.get(key)
            return await asyncio.to_thread(self._cache.get, key)
        except Exception as e:
            logger.warning(f"DiskCache get error: {e}")
            return None

    async def set(self, key: str, value: dict, expire: Optional[int] = None) -> None:
        """Асинхронно сохраняет результат в кэш (I/O в thread pool)."""
        try:
            expire = expire or int(self.ttl.total_seconds())
            if self._in_memory:
                self._cache[key] = value
            else:
                await asyncio.to_thread(self._cache.set, key, value, expire=expire)
        except Exception as e:
            logger.warning(f"DiskCache set error: {e}")


class RedisCache(CacheLevel):
    """L2: Распределённый Redis кэш."""

    def __init__(self, redis_url: Optional[str] = None, ttl_hours: int = 24):
        super().__init__("redis", ttl_hours)
        self._client = None
        if redis_url:
            try:
                import redis.asyncio as aioredis
                self._client = aioredis.from_url(redis_url)
            except Exception as e:
                logger.warning(f"Redis init error: {e}")

    async def get(self, key: str) -> Optional[dict]:
        """Асинхронно получает результат из Redis."""
        if not self._client:
            return None
        try:
            data = await self._client.get(key)
            return json.loads(data) if data else None
        except Exception as e:
            logger.warning(f"Redis get error: {e}")
            return None

    async def set(self, key: str, value: dict, expire: Optional[int] = None) -> None:
        """Асинхронно сохраняет результат в Redis."""
        if not self._client:
            return
        try:
            expire = expire or int(self.ttl.total_seconds())
            await self._client.setex(key, expire, json.dumps(value))
        except Exception as e:
            logger.warning(f"Redis set error: {e}")


class CacheManager:
    """Менеджер кэша с поддержкой L1+L2 уровней, OpenTelemetry tracing и Prometheus метриками.

    Стратегия поиска: L1 (diskcache) → L2 (Redis) → miss.

    Метрики:
        - ``swarm_cache_hits_total`` — счётчик попаданий по слоям
        - ``swarm_cache_misses_total`` — счётчик промахов по слоям
        - ``swarm_cache_operations_total`` — счётчик операций (get/set)
        - ``swarm_cache_latency_seconds`` — гистограмма задержек
        - ``swarm_cache_hit_ratio`` — hit ratio по слоям
    """

    def __init__(self, config: "ScaleConfig"):
        self.l1 = DiskCache(
            directory=config.cache_dir,
            ttl_hours=config.cache_ttl_hours,
            max_size_gb=config.cache_size_gb,
        )
        self.l2 = RedisCache(
            redis_url=config.redis_url,
            ttl_hours=config.cache_ttl_hours,
        )
        self.hits = {"l1": 0, "l2": 0, "miss": 0}
        self._tracer = get_tracer("swarm-cache")
        self._metrics = SwarmMetrics()

    def make_key(self, task: "Task", profile_id: Optional[str] = None) -> str:
        """Создаёт ключ кэша для задачи."""
        return self.l1.make_key(task, profile_id)

    async def get(self, task: "Task", profile_id: Optional[str] = None) -> Optional[dict]:
        """Ищет результат во всех уровнях кэша. L1 → L2 → miss."""
        self._metrics.record_cache_operation("get")
        span_name = "cache.get"
        if self._tracer is not None:
            with self._tracer.start_as_current_span(
                span_name,
                attributes={
                    "cache.content_length": len(task.content),
                    "cache.task_id": task.task_id,
                },
            ) as span:
                return await self._do_get(task, profile_id, span)
        else:
            return await self._do_get(task, profile_id, None)

    async def _do_get(self, task: "Task", profile_id: Optional[str] = None, span=None) -> Optional[dict]:
        """Внутренний метод get с опциональным span и метриками."""
        key = self.make_key(task, profile_id)
        if span is not None:
            span.set_attribute("cache.key", key)

        # L1: локальный кэш
        start = time.time()
        result = await self.l1.get(key)
        l1_latency = time.time() - start
        self._metrics.record_cache_latency("get", "l1", l1_latency)
        if span is not None:
            span.set_attribute("cache.l1_latency", l1_latency)

        if result:
            self.hits["l1"] += 1
            self._metrics.record_cache_hit("l1")
            self._update_hit_ratio("l1")
            if span is not None:
                span.set_attribute("cache.layer", "l1")
                span.set_attribute("cache.hit", True)
            logger.info(f"Cache L1 HIT: {key[:16]}...")
            return result

        self._metrics.record_cache_miss("l1")
        self._update_hit_ratio("l1")

        # L2: проверка Redis
        if self.l2 is not None:
            try:
                start = time.time()
                l2_result = await self.l2.get(key)
                l2_latency = time.time() - start
                self._metrics.record_cache_latency("get", "l2", l2_latency)
                if span is not None:
                    span.set_attribute("cache.l2_latency", l2_latency)

                if l2_result is not None:
                    self.hits["l2"] += 1
                    self._metrics.record_cache_hit("l2")
                    self._update_hit_ratio("l2")
                    if span is not None:
                        span.set_attribute("cache.layer", "l2")
                        span.set_attribute("cache.hit", True)
                    logger.info(f"Cache L2 HIT: {key[:16]}...")
                    return l2_result

                self._metrics.record_cache_miss("l2")
                self._update_hit_ratio("l2")
            except Exception as e:
                if span is not None:
                    span.record_exception(e)
                logger.warning("L2 cache unavailable")

        self.hits["miss"] += 1
        if span is not None:
            span.set_attribute("cache.hit", False)
        return None

    async def set(self, task: "Task", result: dict, profile_id: Optional[str] = None) -> None:
        """Сохраняет результат во все уровни кэша."""
        self._metrics.record_cache_operation("set")
        span_name = "cache.set"
        if self._tracer is not None:
            with self._tracer.start_as_current_span(span_name) as span:
                await self._do_set(task, result, profile_id, span)
        else:
            await self._do_set(task, result, profile_id, None)

    async def _do_set(self, task: "Task", result: dict, profile_id: Optional[str] = None, span=None) -> None:
        """Внутренний метод set с опциональным span и метриками."""
        key = self.make_key(task, profile_id)
        if span is not None:
            span.set_attribute("cache.key", key)

        start = time.time()
        await self.l1.set(key, result)
        l1_latency = time.time() - start
        self._metrics.record_cache_latency("set", "l1", l1_latency)

        # L2: сохраняем в Redis
        if self.l2 is not None:
            try:
                start = time.time()
                await self.l2.set(key, result)
                l2_latency = time.time() - start
                self._metrics.record_cache_latency("set", "l2", l2_latency)
            except Exception as e:
                if span is not None:
                    span.record_exception(e)
                logger.warning("Failed to write to L2 cache")

    def _update_hit_ratio(self, layer: str) -> None:
        """Обновляет hit ratio gauge для указанного слоя на основе счётчиков."""
        hits = self._metrics.get_cache_hit_count(layer)
        misses = self._metrics.get_cache_miss_count(layer)
        total = hits + misses
        if total > 0:
            ratio = hits / total
        else:
            ratio = 0.0
        self._metrics.update_cache_hit_ratio(layer, ratio)

    def stats(self) -> dict:
        """Возвращает статистику кэша, включая метрики Prometheus."""
        total = sum(self.hits.values())
        # Добавляем данные из Prometheus метрик
        l1_hits = self._metrics.get_cache_hit_count("l1")
        l1_misses = self._metrics.get_cache_miss_count("l1")
        l2_hits = self._metrics.get_cache_hit_count("l2")
        l2_misses = self._metrics.get_cache_miss_count("l2")

        l1_total = l1_hits + l1_misses
        l2_total = l2_hits + l2_misses

        return {
            **self.hits,
            "l1_hits_prom": l1_hits,
            "l1_misses_prom": l1_misses,
            "l2_hits_prom": l2_hits,
            "l2_misses_prom": l2_misses,
            "l1_hit_rate_pct": round(l1_hits / max(l1_total, 1) * 100, 1),
            "l2_hit_rate_pct": round(l2_hits / max(l2_total, 1) * 100, 1),
            "hit_rate_pct": round((self.hits.get("l2", 0) + self.hits["l1"]) / max(total, 1) * 100, 1),
        }
