"""Реализация провайдера LLM через LiteLLM.

LiteLLM — это AI Gateway, который предоставляет единый интерфейс
для 100+ LLM провайдеров (DeepSeek, OpenAI, Anthropic, Groq, и др.).

Особенности:
    - Fallback: при падении DeepSeek автоматически переключается на Groq
    - Rate limiting: встроенное ограничение RPM (requests per minute)
    - Маршрутизация: latency-based routing для минимальной задержки
    - Prompt compression: опциональное сжатие промптов через LLMLingua
    - OpenTelemetry tracing: каждый LLM вызов отслеживается
"""

import os
import time
from typing import Optional

from litellm import Router, acompletion, token_counter

from .base import BaseLLMProvider, LLMResponse
from .config import LiteLLMConfig
from ..prompt_compression import SwarmPromptCompressor
from ..tracing import get_tracer as _get_tracer


class LiteLLMProvider(BaseLLMProvider):
    """Провайдер LLM на базе LiteLLM Router.

    Поддерживает fallback, rate limiting, маршрутизацию,
    опциональное сжатие промптов и OpenTelemetry tracing.

    Пример использования:
        provider = LiteLLMProvider()
        response = await provider.generate(
            messages=[{"role": "user", "content": "Hello!"}],
            model="deepseek-chat",
        )
        print(response.content)
    """

    def __init__(
        self,
        config: Optional[LiteLLMConfig] = None,
        compressor: Optional[SwarmPromptCompressor] = None,
    ):
        """Инициализирует LiteLLMProvider.

        Args:
            config: конфигурация LiteLLM (если None, загружается из env)
            compressor: компрессор промптов (если None, создаётся из config)
        """
        self._config = config or LiteLLMConfig.from_env()
        self._router = self._build_router()

        # Настройка компрессора промптов
        if compressor is not None:
            self._compressor = compressor
        elif self._config.compression_enabled:
            self._compressor = SwarmPromptCompressor(
                rate=self._config.compression_rate,
                min_tokens=self._config.compression_min_tokens,
            )
        else:
            self._compressor = None

        # Инициализация трейсера
        self._tracer = _get_tracer("swarm-llm")

    # ------------------------------------------------------------------ #
    # Публичные методы
    # ------------------------------------------------------------------ #

    async def generate(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Генерирует ответ через LiteLLM Router.

        Перед отправкой сообщения могут быть сжаты компрессором промптов.
        Сжатие НЕ применяется для reasoning моделей (deepseek-reasoner) —
        они сами оптимизируют контекст.

        Args:
            messages: список сообщений
            model: логическое имя модели (deepseek-chat, deepseek-reasoner)
            temperature: температура генерации
            max_tokens: максимальное количество токенов

        Returns:
            LLMResponse: структурированный ответ
        """
        model_name = model or "deepseek-chat"

        # Создаём span для отслеживания LLM вызова
        if self._tracer is not None:
            with self._tracer.start_as_current_span(
                "llm.generate",
                attributes={
                    "llm.model": model_name,
                    "llm.temperature": temperature,
                    "llm.max_tokens": max_tokens or 0,
                    "llm.messages_count": len(messages),
                    "llm.compressor_enabled": self._compressor is not None,
                },
            ) as span:
                return await self._do_generate(
                    messages, model_name, temperature, max_tokens, span
                )
        else:
            return await self._do_generate(
                messages, model_name, temperature, max_tokens, None
            )

    async def _do_generate(
        self,
        messages: list[dict[str, str]],
        model_name: str,
        temperature: float,
        max_tokens: Optional[int],
        span=None,
    ) -> LLMResponse:
        """Внутренний метод генерации с опциональным span."""
        # Сжимаем промпт перед отправкой (кроме reasoning моделей)
        if self._compressor is not None and model_name != "deepseek-reasoner":
            messages = self._compressor.compress_messages(messages)
            if span is not None:
                span.set_attribute("llm.compressed", True)
                span.set_attribute("llm.messages_after_compression", len(messages))

        kwargs = {
            "model": model_name,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens:
            kwargs["max_tokens"] = max_tokens

        start = time.time()
        response = await self._router.acompletion(**kwargs)
        latency = time.time() - start

        usage = response.get("usage", {})

        # Добавляем атрибуты в span после вызова
        if span is not None:
            span.set_attribute("llm.prompt_tokens", usage.get("prompt_tokens", 0))
            span.set_attribute("llm.completion_tokens", usage.get("completion_tokens", 0))
            span.set_attribute("llm.total_tokens", usage.get("total_tokens", 0))
            span.set_attribute("llm.latency_seconds", latency)

            if latency > 10:
                span.set_attribute("llm.slow", True)
                span.add_event("slow_llm_response", {"latency": latency})

        # Извлекаем content из ответа
        choices = response.get("choices", [])
        content = ""
        if choices:
            content = choices[0].get("message", {}).get("content", "")

        return LLMResponse(
            content=content,
            model=model_name,
            provider="litellm",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_seconds=latency,
        )

    def count_tokens(self, messages: list[dict[str, str]], model: Optional[str] = None) -> int:
        """Подсчитывает количество токенов.

        Args:
            messages: список сообщений
            model: имя модели

        Returns:
            int: количество токенов
        """
        return token_counter(messages=messages, model=model or "deepseek-chat")

    @property
    def provider_name(self) -> str:
        """Возвращает имя провайдера."""
        return "litellm"

    @property
    def compressor(self) -> Optional[SwarmPromptCompressor]:
        """Возвращает компрессор промптов."""
        return self._compressor

    # ------------------------------------------------------------------ #
    # Внутренние методы
    # ------------------------------------------------------------------ #

    def _build_router(self) -> Router:
        """Создаёт и настраивает LiteLLM Router.

        Returns:
            Router: настроенный экземпляр Router
        """
        cfg = self._config
        model_list = []

        # DeepSeek primary — deepseek-chat
        if cfg.deepseek_api_key:
            model_list.append({
                "model_name": "deepseek-chat",
                "litellm_params": {
                    "model": "deepseek/deepseek-chat",
                    "api_key": cfg.deepseek_api_key,
                    "rpm": cfg.deepseek_rpm,
                },
            })

            # DeepSeek Reasoner для сложных задач
            model_list.append({
                "model_name": "deepseek-reasoner",
                "litellm_params": {
                    "model": "deepseek/deepseek-reasoner",
                    "api_key": cfg.deepseek_api_key,
                    "rpm": cfg.deepseek_rpm,
                },
            })

        # Groq fallback для deepseek-chat
        if cfg.groq_api_key:
            model_list.append({
                "model_name": "deepseek-chat",  # то же логическое имя
                "litellm_params": {
                    "model": "groq/llama3-70b-8192",
                    "api_key": cfg.groq_api_key,
                    "rpm": cfg.groq_rpm,
                },
            })

        # Если нет ни одного ключа, добавляем заглушку
        if not model_list:
            model_list.append({
                "model_name": "deepseek-chat",
                "litellm_params": {
                    "model": "deepseek/deepseek-chat",
                    "api_key": "sk-placeholder",
                    "rpm": 1,
                },
            })

        fallbacks = [
            {"deepseek-chat": cfg.fallback_models}
        ] if cfg.fallback_models else []

        return Router(
            model_list=model_list,
            fallbacks=fallbacks,
            routing_strategy=cfg.routing_strategy,
            num_retries=cfg.num_retries,
            retry_after=cfg.retry_after,
        )

    @classmethod
    def from_config(cls, config: LiteLLMConfig) -> "LiteLLMProvider":
        """Создаёт провайдер из готовой конфигурации.

        Args:
            config: конфигурация LiteLLM

        Returns:
            LiteLLMProvider: настроенный провайдер
        """
        return cls(config=config)
