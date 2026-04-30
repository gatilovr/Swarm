"""OpenTelemetry tracing для Swarm проекта.

Предоставляет единую точку настройки OpenTelemetry для всех компонентов:
- swarm (core)
- swarm-mcp
- swarm-scale

Поддерживает:
- OTLP gRPC экспорт (продакшн)
- Console экспорт (разработка, если OTLP endpoint не задан)
- Graceful degradation если OpenTelemetry не установлен
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Попытка импорта OpenTelemetry
try:
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.resources import Resource

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False
    trace = None  # type: ignore
    TracerProvider = None  # type: ignore
    BatchSpanProcessor = None  # type: ignore
    ConsoleSpanExporter = None  # type: ignore
    Resource = None  # type: ignore


def setup_tracing(
    service_name: str = "swarm",
    otlp_endpoint: Optional[str] = None,
    environment: Optional[str] = None,
) -> Optional["trace.Tracer"]:
    """Настраивает OpenTelemetry и возвращает Tracer.

    Args:
        service_name: имя сервиса (swarm, swarm-mcp, swarm-scale)
        otlp_endpoint: OTLP gRPC endpoint (default: env OTEL_EXPORTER_OTLP_ENDPOINT)
        environment: окружение (default: env OTEL_ENVIRONMENT or "development")

    Returns:
        Tracer для создания спанов, или None если OpenTelemetry не установлен
    """
    if not _OTEL_AVAILABLE:
        logger.warning(
            "OpenTelemetry не установлен. Установите opentelemetry-api, "
            "opentelemetry-sdk, opentelemetry-exporter-otlp-proto-grpc для трассировки."
        )
        return None

    otlp_endpoint = otlp_endpoint or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    environment = environment or os.getenv("OTEL_ENVIRONMENT", "development")

    resource = Resource.create({
        "service.name": service_name,
        "service.version": "0.2.0",
        "deployment.environment": environment,
    })

    provider = TracerProvider(resource=resource)

    if otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            logger.info(
                "OTLP экспорт включён: endpoint=%s, service=%s, env=%s",
                otlp_endpoint, service_name, environment,
            )
        except ImportError:
            logger.warning(
                "opentelemetry-exporter-otlp-proto-grpc не установлен. "
                "Падаем на ConsoleSpanExporter."
            )
            _add_console_exporter(provider)
    else:
        _add_console_exporter(provider)

    # Устанавливаем глобальный провайдер
    trace.set_tracer_provider(provider)

    return provider.get_tracer(service_name, "0.2.0")


def _add_console_exporter(provider) -> None:
    """Добавляет ConsoleSpanExporter для разработки."""
    exporter = ConsoleSpanExporter()
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    logger.info("Console экспорт включён (OTLP endpoint не задан).")


def get_tracer(service_name: str = "swarm") -> Optional["trace.Tracer"]:
    """Возвращает Tracer для указанного сервиса.

    Args:
        service_name: имя сервиса

    Returns:
        Tracer или NoopTracer если OpenTelemetry не установлен
    """
    if not _OTEL_AVAILABLE:
        return None

    try:
        provider = trace.get_tracer_provider()
        return provider.get_tracer(service_name, "0.2.0")
    except Exception:
        return None


# Проверка доступности
def is_tracing_enabled() -> bool:
    """Возвращает True если OpenTelemetry доступен и настроен."""
    return _OTEL_AVAILABLE


__all__ = [
    "setup_tracing",
    "get_tracer",
    "is_tracing_enabled",
]
