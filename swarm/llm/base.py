"""Абстрактный базовый класс для провайдеров LLM."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMResponse:
    """Структурированный ответ от LLM.

    Поля:
        content: текстовый ответ модели
        model: имя модели
        provider: имя провайдера (litellm, openai, anthropic, ...)
        prompt_tokens: количество токенов в запросе
        completion_tokens: количество токенов в ответе
        total_tokens: общее количество токенов
        latency_seconds: задержка выполнения в секундах
    """
    content: str
    model: str
    provider: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_seconds: float = 0.0


class BaseLLMProvider(ABC):
    """Абстрактный провайдер LLM.

    Все конкретные реализации (LiteLLM, OpenAI, Anthropic и т.д.)
    должны наследоваться от этого класса.
    """

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Генерирует ответ от LLM.

        Args:
            messages: список сообщений [{"role": "user", "content": "..."}, ...]
            model: имя модели (если None, используется модель по умолчанию)
            temperature: температура генерации (0.0 — 2.0)
            max_tokens: максимальное количество токенов в ответе

        Returns:
            LLMResponse: структурированный ответ модели
        """
        ...

    @abstractmethod
    def count_tokens(self, messages: list[dict[str, str]], model: Optional[str] = None) -> int:
        """Подсчитывает количество токенов в сообщениях.

        Args:
            messages: список сообщений
            model: имя модели (если None, используется модель по умолчанию)

        Returns:
            int: количество токенов
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Возвращает имя провайдера (litellm, openai, anthropic, ...)."""
        ...
