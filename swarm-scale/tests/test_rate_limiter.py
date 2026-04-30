"""Тесты для адаптивного rate limiter."""

import pytest
from swarm_scale.rate_limiter import AdaptiveRateLimiter


class TestAdaptiveRateLimiter:
    """Тесты AdaptiveRateLimiter."""

    @pytest.mark.asyncio
    async def test_acquire(self):
        """Получение слота rate limiter."""
        limiter = AdaptiveRateLimiter(max_rpm=500)
        wait = await limiter.acquire()
        assert wait == 0.0
        assert limiter.current_rpm == 500

    @pytest.mark.asyncio
    async def test_report_429(self):
        """Снижение RPM после 429 ошибки."""
        limiter = AdaptiveRateLimiter(max_rpm=500)
        await limiter.acquire()

        limiter.report_429()
        assert limiter.current_rpm == 250  # 500 // 2

        # Повторный 429
        limiter.report_429()
        assert limiter.current_rpm == 125  # 250 // 2

        # Многократный 429 не должен опустить ниже 10
        for _ in range(10):
            limiter.report_429()
        assert limiter.current_rpm == 10  # минимум

    @pytest.mark.asyncio
    async def test_report_success(self):
        """Восстановление RPM после успешных запросов."""
        limiter = AdaptiveRateLimiter(max_rpm=500)

        # Сначала снижаем RPM
        limiter.report_429()
        assert limiter.current_rpm == 250

        # 10 успешных запросов должны восстановить на 10 RPM
        for _ in range(10):
            limiter.report_success()

        assert limiter.current_rpm == 260  # 250 + 10

        # Ещё 10 успешных
        for _ in range(10):
            limiter.report_success()

        assert limiter.current_rpm == 270

    @pytest.mark.asyncio
    async def test_stats(self):
        """Проверка статистики."""
        limiter = AdaptiveRateLimiter(max_rpm=500)
        await limiter.acquire()

        stats = limiter.stats
        assert stats["current_rpm"] == 500
        assert stats["max_rpm"] == 500
        assert stats["active_calls"] == 1
        assert stats["last_429"] is False

        limiter.report_429()
        stats = limiter.stats
        assert stats["current_rpm"] == 250
        assert stats["last_429"] is True
