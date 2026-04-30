"""Тесты для модуля Prometheus метрик."""

from unittest.mock import patch
import pytest

from swarm_scale.metrics import (
    tasks_total,
    tokens_total,
    cost_total,
    active_workers,
    queue_depth,
    cache_size,
    rpm_current,
    record_task_completed,
    record_task_failed,
    record_task_cached,
    record_tokens,
    record_cost,
    start_metrics_server,
)


# Prometheus-метрики глобальны — все тесты используют before/after
# для корректной работы с накопленными значениями.


class TestTaskCounters:
    """Тесты счётчиков задач."""

    def test_record_task_completed(self):
        """Инкремент completed."""
        before = tasks_total.labels(status="completed")._value.get()
        record_task_completed(duration_sec=1.5)
        after = tasks_total.labels(status="completed")._value.get()
        assert after == before + 1

    def test_record_task_failed(self):
        """Инкремент failed."""
        before = tasks_total.labels(status="failed")._value.get()
        record_task_failed()
        after = tasks_total.labels(status="failed")._value.get()
        assert after == before + 1

    def test_record_task_cached(self):
        """Инкремент cached."""
        before = tasks_total.labels(status="cached")._value.get()
        record_task_cached()
        after = tasks_total.labels(status="cached")._value.get()
        assert after == before + 1

    def test_multiple_records(self):
        """Несколько записей разных статусов."""
        completed_before = tasks_total.labels(status="completed")._value.get()
        failed_before = tasks_total.labels(status="failed")._value.get()
        cached_before = tasks_total.labels(status="cached")._value.get()

        record_task_completed(duration_sec=1.0)
        record_task_completed(duration_sec=2.0)
        record_task_failed()
        record_task_cached()
        record_task_cached()

        assert tasks_total.labels(status="completed")._value.get() == completed_before + 2
        assert tasks_total.labels(status="failed")._value.get() == failed_before + 1
        assert tasks_total.labels(status="cached")._value.get() == cached_before + 2

    def test_metrics_independence(self):
        """Статусы не влияют друг на друга."""
        completed_before = tasks_total.labels(status="completed")._value.get()
        failed_before = tasks_total.labels(status="failed")._value.get()

        record_task_completed(duration_sec=1.0)

        assert tasks_total.labels(status="completed")._value.get() == completed_before + 1
        # failed не должен измениться
        assert tasks_total.labels(status="failed")._value.get() == failed_before


class TestTokenAndCostMetrics:
    """Тесты метрик токенов и стоимости."""

    def test_record_tokens(self):
        """Запись токенов с label модели."""
        before = tokens_total.labels(model="deepseek-chat")._value.get()
        record_tokens(model="deepseek-chat", count=150)
        after = tokens_total.labels(model="deepseek-chat")._value.get()
        assert after == before + 150

    def test_record_tokens_multiple_models(self):
        """Разные модели считаются раздельно."""
        chat_before = tokens_total.labels(model="deepseek-chat")._value.get()
        reasoner_before = tokens_total.labels(model="deepseek-reasoner")._value.get()

        record_tokens(model="deepseek-chat", count=100)
        record_tokens(model="deepseek-reasoner", count=200)

        assert tokens_total.labels(model="deepseek-chat")._value.get() == chat_before + 100
        assert tokens_total.labels(model="deepseek-reasoner")._value.get() == reasoner_before + 200

    def test_record_cost(self):
        """Запись стоимости."""
        before = cost_total._value.get()
        record_cost(0.05)
        after = cost_total._value.get()
        assert after == before + 0.05

    def test_record_cost_accumulation(self):
        """Стоимость суммируется."""
        before = cost_total._value.get()
        record_cost(0.01)
        record_cost(0.02)
        record_cost(0.03)
        assert cost_total._value.get() == before + 0.06


class TestGauges:
    """Тесты gauge-метрик."""

    def test_active_workers(self):
        """Gauge активных воркеров."""
        active_workers.set(5)
        assert active_workers._value.get() == 5
        active_workers.set(10)
        assert active_workers._value.get() == 10

    def test_queue_depth(self):
        """Gauge глубины очереди."""
        queue_depth.set(42)
        assert queue_depth._value.get() == 42
        queue_depth.dec()
        assert queue_depth._value.get() == 41

    def test_cache_size(self):
        """Gauge размера кэша."""
        cache_size.set(1024 * 1024)
        assert cache_size._value.get() == 1024 * 1024

    def test_rpm_current(self):
        """Gauge текущего RPM."""
        rpm_current.set(500)
        assert rpm_current._value.get() == 500
        rpm_current.set(250)
        assert rpm_current._value.get() == 250

    def test_gauge_inc_dec(self):
        """Инкремент и декремент gauge."""
        active_workers.set(0)
        active_workers.inc()
        assert active_workers._value.get() == 1
        active_workers.inc(3)
        assert active_workers._value.get() == 4
        active_workers.dec(2)
        assert active_workers._value.get() == 2


class TestMetricsServer:
    """Тесты HTTP-сервера метрик."""

    @patch("swarm_scale.metrics.start_http_server")
    def test_start_metrics_server_default_port(self, mock_start):
        """Сервер запускается на порту по умолчанию (8000)."""
        start_metrics_server()
        mock_start.assert_called_once_with(8000)

    @patch("swarm_scale.metrics.start_http_server")
    def test_start_metrics_server_custom_port(self, mock_start):
        """Сервер запускается на указанном порту."""
        start_metrics_server(port=9090)
        mock_start.assert_called_once_with(9090)

    @patch("swarm_scale.metrics.start_http_server")
    def test_start_metrics_server_can_be_called_multiple(self, mock_start):
        """Можно вызвать несколько раз с разными портами."""
        start_metrics_server(8000)
        start_metrics_server(8001)
        assert mock_start.call_count == 2
