"""Property-based тесты для адаптивного rate limiter.

Инварианты:
- RateLimiter никогда не опускается ниже MIN_RPM
- RateLimiter никогда не поднимается выше max_rpm
- После N успешных вызовов RPM увеличивается
- После rate limit RPM уменьшается
"""
import pytest
from hypothesis import given, strategies as st
from swarm_scale.rate_limiter import AdaptiveRateLimiter


class TestRateLimiterProperties:
    """Property-based тесты AdaptiveRateLimiter."""

    @given(
        max_rpm=st.integers(min_value=10, max_value=1000),
    )
    def test_rate_limiter_initial_state(self, max_rpm):
        """RateLimiter инициализируется корректно для любого max_rpm."""
        limiter = AdaptiveRateLimiter(max_rpm=max_rpm)
        assert limiter.current_rpm == max_rpm
        assert limiter.max_rpm == max_rpm
        # Приватное поле, но доступно для тестов
        assert limiter._consecutive_successes == 0

    @given(
        max_rpm=st.integers(min_value=20, max_value=1000),
        backoffs=st.integers(min_value=1, max_value=20),
    )
    def test_rate_limiter_adapts_down(self, max_rpm, backoffs):
        """После N rate limits RPM уменьшается, но не ниже MIN_RPM."""
        limiter = AdaptiveRateLimiter(max_rpm=max_rpm)
        for _ in range(backoffs):
            limiter.report_429()
        assert limiter.current_rpm >= AdaptiveRateLimiter.MIN_RPM
        assert limiter.current_rpm <= max_rpm
        # Хотя бы один backoff должен был сработать
        if backoffs > 0:
            assert limiter.current_rpm <= max_rpm // 2 or max_rpm <= AdaptiveRateLimiter.MIN_RPM * 2

    @given(
        max_rpm=st.integers(min_value=50, max_value=500),
        successes=st.integers(min_value=1, max_value=50),
    )
    def test_rate_limiter_adapts_up_after_success(self, max_rpm, successes):
        """После N успешных вызовов RPM может увеличиться (если был сброшен)."""
        limiter = AdaptiveRateLimiter(max_rpm=max_rpm)
        # Сначала снижаем RPM
        limiter.report_429()
        current_after_429 = limiter.current_rpm

        # Теперь делаем успешные вызовы
        for _ in range(successes):
            limiter.report_success()

        # RPM должен быть >= чем после 429 (но не больше max_rpm)
        assert limiter.current_rpm >= current_after_429
        assert limiter.current_rpm <= max_rpm

    @given(
        max_rpm=st.integers(min_value=10, max_value=100),
        n_ops=st.integers(min_value=0, max_value=30),
    )
    def test_rate_limiter_rpm_bounds(self, max_rpm, n_ops):
        """RateLimiter RPM всегда в [MIN_RPM, max_rpm]."""
        limiter = AdaptiveRateLimiter(max_rpm=max_rpm)

        # Симулируем чередующиеся 429 и success
        for i in range(n_ops):
            if i % 3 == 0:
                limiter.report_429()
            elif i % 3 == 1:
                limiter.report_success()
            # i % 3 == 2 — ничего не делаем
            # Проверяем границы после каждой операции
            assert limiter.current_rpm >= AdaptiveRateLimiter.MIN_RPM
            assert limiter.current_rpm <= max_rpm

    @given(
        max_rpm=st.integers(min_value=10, max_value=100),
    )
    def test_rate_limiter_min_rpm_invariant(self, max_rpm):
        """RateLimiter не опускается ниже MIN_RPM даже при множественных 429."""
        limiter = AdaptiveRateLimiter(max_rpm=max_rpm)
        for _ in range(100):
            limiter.report_429()
        assert limiter.current_rpm >= AdaptiveRateLimiter.MIN_RPM

    @given(
        max_rpm=st.integers(min_value=11, max_value=100),
    )
    def test_rate_limiter_stats_consistency(self, max_rpm):
        """Статистика rate limiter'а всегда консистентна."""
        limiter = AdaptiveRateLimiter(max_rpm=max_rpm)
        stats = limiter.stats

        assert stats["current_rpm"] == max_rpm
        assert stats["max_rpm"] == max_rpm
        assert stats["active_calls"] == 0
        assert stats["last_429"] is False

        # После 429 (max_rpm > MIN_RPM, поэтому RPM уменьшится)
        limiter.report_429()
        stats = limiter.stats
        assert stats["current_rpm"] < max_rpm
        assert stats["last_429"] is True

    @given(
        max_rpm=st.integers(min_value=10, max_value=10),
    )
    def test_rate_limiter_stats_at_min_rpm(self, max_rpm):
        """При max_rpm == MIN_RPM, report_429() не уменьшает ниже MIN_RPM."""
        limiter = AdaptiveRateLimiter(max_rpm=max_rpm)
        limiter.report_429()
        stats = limiter.stats
        assert stats["current_rpm"] == AdaptiveRateLimiter.MIN_RPM
        assert stats["last_429"] is True

    @pytest.mark.asyncio
    @given(
        max_rpm=st.integers(min_value=50, max_value=500),
    )
    async def test_rate_limiter_acquire_returns_float(self, max_rpm):
        """acquire() всегда возвращает float (время ожидания)."""
        limiter = AdaptiveRateLimiter(max_rpm=max_rpm)
        wait = await limiter.acquire()
        assert isinstance(wait, float)
        assert wait >= 0.0

    @pytest.mark.asyncio
    @given(
        max_rpm=st.integers(min_value=50, max_value=200),
        n_calls=st.integers(min_value=1, max_value=5),
    )
    async def test_rate_limiter_concurrent_calls(self, max_rpm, n_calls):
        """Множественные acquire() не ломают счётчик."""
        limiter = AdaptiveRateLimiter(max_rpm=max_rpm)
        for _ in range(n_calls):
            await limiter.acquire()

        stats = limiter.stats
        # active_calls должно быть <= n_calls (окно 60 секунд)
        assert stats["active_calls"] == n_calls
        assert stats["current_rpm"] == max_rpm
