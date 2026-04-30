"""Конфигурация для LiteLLM Router."""

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LiteLLMConfig:
    """Конфигурация для LiteLLM Router.

    Поля:
        deepseek_api_key: API-ключ DeepSeek
        groq_api_key: API-ключ Groq
        openai_api_key: API-ключ OpenAI
        anthropic_api_key: API-ключ Anthropic
        deepseek_base_url: базовый URL для DeepSeek API
        deepseek_rpm: лимит запросов в минуту для DeepSeek
        groq_rpm: лимит запросов в минуту для Groq
        fallback_models: список fallback-моделей для deepseek-chat
        routing_strategy: стратегия маршрутизации LiteLLM
        num_retries: количество повторных попыток
        retry_after: секунд ожидания перед повтором

        compression_enabled: включить сжатие промптов
        compression_rate: коэффициент сжатия (0.0-1.0)
        compression_min_tokens: минимальный размер контекста для сжатия
    """

    deepseek_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    deepseek_base_url: Optional[str] = None
    deepseek_rpm: int = 500
    groq_rpm: int = 30
    fallback_models: list[str] = field(default_factory=lambda: ["groq/llama3-70b-8192"])
    routing_strategy: str = "latency-based-routing"
    num_retries: int = 2
    retry_after: int = 5

    # Prompt compression (LLMLingua)
    compression_enabled: bool = True
    compression_rate: float = 0.5
    compression_min_tokens: int = 4096

    @classmethod
    def from_env(cls) -> "LiteLLMConfig":
        """Загружает конфигурацию из переменных окружения.

        Returns:
            LiteLLMConfig: загруженная конфигурация
        """
        return cls(
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
            groq_api_key=os.getenv("GROQ_API_KEY"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
            deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL"),
            deepseek_rpm=int(os.getenv("DEEPSEEK_RPM", "500")),
            groq_rpm=int(os.getenv("GROQ_RPM", "30")),
            compression_enabled=os.getenv("COMPRESSION_ENABLED", "true").lower() == "true",
            compression_rate=float(os.getenv("COMPRESSION_RATE", "0.5")),
            compression_min_tokens=int(os.getenv("COMPRESSION_MIN_TOKENS", "4096")),
        )
