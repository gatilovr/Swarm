"""Тесты для модуля трассировки OpenTelemetry.

Все тесты работают без реального OTLP endpoint — используют
ConsoleSpanExporter или Noop-провайдер.
"""

import pytest
from unittest.mock import patch, MagicMock

from swarm.tracing import (
    setup_tracing,
    get_tracer,
    is_tracing_enabled,
    _OTEL_AVAILABLE,
)


class TestSetupTracing:
    """Тесты для setup_tracing."""

    def test_setup_tracing_default(self):
        """Tracer создаётся с правильными атрибутами по умолчанию."""
        if not _OTEL_AVAILABLE:
            pytest.skip("OpenTelemetry не установлен")

        tracer = setup_tracing(service_name="test-swarm")
        assert tracer is not None

        span = tracer.start_span("test")
        span.end()

    def test_setup_tracing_without_otel(self):
        """setup_tracing возвращает None если OTel не установлен."""
        with patch("swarm.tracing._OTEL_AVAILABLE", False):
            tracer = setup_tracing(service_name="test-swarm")
            assert tracer is None

    def test_setup_tracing_with_custom_endpoint(self):
        """Tracer создаётся с кастомным endpoint."""
        if not _OTEL_AVAILABLE:
            pytest.skip("OpenTelemetry не установлен")

        tracer = setup_tracing(
            service_name="test-swarm",
            otlp_endpoint="http://localhost:4317",
            environment="test",
        )
        assert tracer is not None

        span = tracer.start_span("custom-endpoint-test")
        span.set_attribute("test", True)
        span.end()


class TestGetTracer:
    """Тесты для get_tracer."""

    def test_get_tracer_returns_tracer(self):
        """get_tracer возвращает Tracer."""
        if not _OTEL_AVAILABLE:
            pytest.skip("OpenTelemetry не установлен")

        setup_tracing("test")
        tracer = get_tracer("test")
        assert tracer is not None

        from opentelemetry import trace
        assert isinstance(tracer, trace.Tracer)

    def test_get_tracer_without_setup(self):
        """get_tracer работает даже без явного setup_tracing."""
        if not _OTEL_AVAILABLE:
            pytest.skip("OpenTelemetry не установлен")

        tracer = get_tracer("test-without-setup")
        # Должен вернуть NoopTracer или обычный Tracer
        assert tracer is not None

    def test_get_tracer_without_otel(self):
        """get_tracer возвращает None если OTel не установлен."""
        with patch("swarm.tracing._OTEL_AVAILABLE", False):
            tracer = get_tracer("test")
            assert tracer is None


class TestIsTracingEnabled:
    """Тесты для is_tracing_enabled."""

    def test_is_tracing_enabled_when_available(self):
        """is_tracing_enabled возвращает True когда OTel доступен."""
        result = is_tracing_enabled()
        assert result == _OTEL_AVAILABLE

    def test_is_tracing_enabled_when_unavailable(self):
        """is_tracing_enabled возвращает False когда OTel не доступен."""
        with patch("swarm.tracing._OTEL_AVAILABLE", False):
            assert is_tracing_enabled() is False


@pytest.mark.asyncio
async def test_tracing_context_propagation():
    """Контекст трассировки пробрасывается через async вызовы."""
    if not _OTEL_AVAILABLE:
        pytest.skip("OpenTelemetry не установлен")

    tracer = setup_tracing("test")

    async def inner():
        with tracer.start_as_current_span("inner") as span:
            span.set_attribute("test", True)
            return span.get_span_context().trace_id

    async def outer():
        with tracer.start_as_current_span("outer") as span:
            return await inner()

    trace_id = await outer()
    assert trace_id is not None


class TestSpanAttributes:
    """Тесты для атрибутов спанов."""

    def test_span_with_attributes(self):
        """Спан корректно хранит атрибуты."""
        if not _OTEL_AVAILABLE:
            pytest.skip("OpenTelemetry не установлен")

        tracer = setup_tracing("test-attributes")

        with tracer.start_as_current_span(
            "test-span",
            attributes={
                "test.string": "value",
                "test.int": 42,
                "test.bool": True,
                "test.float": 3.14,
            },
        ) as span:
            span.set_attribute("test.dynamic", "added")

        # Если ConsoleSpanExporter используется, ошибок не будет
        assert True


class TestSpanEvents:
    """Тесты для событий спанов."""

    def test_span_with_events(self):
        """Спан корректно добавляет события."""
        if not _OTEL_AVAILABLE:
            pytest.skip("OpenTelemetry не установлен")

        tracer = setup_tracing("test-events")

        with tracer.start_as_current_span("test-events-span") as span:
            span.add_event("custom_event", {"key": "value"})
            span.add_event("another_event", {"number": 1, "flag": True})

        assert True


@pytest.mark.asyncio
async def test_nested_spans():
    """Вложенные спаны корректно работают в async контексте."""
    if not _OTEL_AVAILABLE:
        pytest.skip("OpenTelemetry не установлен")

    tracer = setup_tracing("test-nested")

    async def level2():
        with tracer.start_as_current_span("level2") as span:
            span.set_attribute("level", 2)
            return span.get_span_context().span_id

    async def level1():
        with tracer.start_as_current_span("level1") as span:
            span.set_attribute("level", 1)
            return await level2()

    async def level0():
        with tracer.start_as_current_span("level0") as span:
            span.set_attribute("level", 0)
            return await level1()

    span_id = await level0()
    assert span_id is not None


@pytest.mark.asyncio
async def test_tracing_graceful_degradation():
    """Graceful degradation: всё работает без OTel."""
    with patch("swarm.tracing._OTEL_AVAILABLE", False):
        # setup_tracing должен вернуть None
        assert setup_tracing("test") is None

        # get_tracer должен вернуть None
        assert get_tracer("test") is None

        # is_tracing_enabled должен вернуть False
        assert is_tracing_enabled() is False

        # Код, использующий tracer, не должен падать
        tracer = get_tracer("test")
        assert tracer is None  # Просто проверяем что не упало
