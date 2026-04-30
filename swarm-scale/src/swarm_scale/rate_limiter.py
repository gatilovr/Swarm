"""Адаптивный rate limiter для API DeepSeek.

Операции rate limiter отслеживаются через OpenTelemetry tracing.
"""

import asyncio
import logging
import time
from collections import deque

from swarm.tracing import get_tracer

logger = logging.getLogger(__name__)


class AdaptiveRateLimiter:
    """Rate limiter с адаптивным backoff при 429 ошибках и OpenTelemetry tracing.

    Автоматически снижает RPM при получении 429 Too Many Requests
    и постепенно увеличивает при успешных запросах.

    Алгоритм:
    - При 429: current_rpm //= BACKOFF_FACTOR (минимум MIN_RPM)
    - После SUCCESS_THRESHOLD успешных запросов: current_rpm += RPM_INCREMENT (максимум max_rpm)
    - acquire() блокируется, если лимит исчерпан на текущую минуту
    """

    MIN_RPM = 10
    SUCCESS_THRESHOLD = 10
    RPM_INCREMENT = 10
    BACKOFF_FACTOR = 2

    def __init__(self, max_rpm: int = 500):
        self.max_rpm = max_rpm
        self.current_rpm = max_rpm
        self._calls = deque()
        self._last_429_at: float = 0
        self._consecutive_successes = 0
        self._lock = asyncio.Lock()
        self._tracer = get_tracer("swarm-ratelimiter")

    async def acquire(self) -> float:
        """Ожидает доступный слот. Возвращает время ожидания в секундах."""
        span_name = "ratelimiter.acquire"
        if self._tracer is not None:
            with self._tracer.start_as_current_span(
                span_name,
                attributes={
                    "ratelimiter.current_rpm": self.current_rpm,
                    "ratelimiter.min_rpm": self.MIN_RPM,
                },
            ) as span:
                return await self._do_acquire(span)
        else:
            return await self._do_acquire(None)

    async def _do_acquire(self, span=None) -> float:
        """Внутренний метод acquire с опциональным span."""
        async with self._lock:
            now = time.time()

            # Очистка вызовов старше 60 секунд
            while self._calls and self._calls[0] < now - 60:
                self._calls.popleft()

            # Рассчитываем время ожидания
            if len(self._calls) >= self.current_rpm:
                wait_time = self._calls[0] + 60 - now
                if wait_time > 0:
                    if span is not None:
                        span.set_attribute("ratelimiter.wait_time", wait_time)
                        span.add_event("rate_limit_wait", {"wait_time": wait_time})
                    await asyncio.sleep(wait_time)

            self._calls.append(time.time())
            return 0.0

    def report_429(self):
        """Сообщает о получении 429 Too Many Requests."""
        self._last_429_at = time.time()
        old_rpm = self.current_rpm
        self.current_rpm = max(self.MIN_RPM, self.current_rpm // self.BACKOFF_FACTOR)
        self._consecutive_successes = 0
        logger.warning(f"Rate limited! RPM: {old_rpm} -> {self.current_rpm}")

    def report_success(self):
        """Сообщает об успешном запросе."""
        self._consecutive_successes += 1
        if self._consecutive_successes >= self.SUCCESS_THRESHOLD and self.current_rpm < self.max_rpm:
            self.current_rpm = min(self.max_rpm, self.current_rpm + self.RPM_INCREMENT)
            self._consecutive_successes = 0

    @property
    def stats(self) -> dict:
        """Возвращает статистику rate limiter."""
        return {
            "current_rpm": self.current_rpm,
            "max_rpm": self.max_rpm,
            "active_calls": len(self._calls),
            "last_429": bool(self._last_429_at),
        }
