"""Базовый класс для всех агентов Swarm."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from opentelemetry.trace import Status, StatusCode

from swarm.llm import BaseLLMProvider, LLMResponse
from swarm.state import SwarmState
from swarm.tracing import get_tracer

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Базовый абстрактный класс для агентов роя.

    Свойства:
        name: имя агента
        llm_provider: провайдер LLM
        model_name: имя модели для вызовов LLM
        system_prompt: системный промпт агента
    """

    def __init__(
        self,
        llm_provider: BaseLLMProvider,
        model_name: Optional[str] = None,
    ) -> None:
        """Инициализирует агента.

        Args:
            llm_provider: экземпляр провайдера LLM
            model_name: имя модели (если None, используется "deepseek-chat")
        """
        self._llm_provider = llm_provider
        self._model_name = model_name or "deepseek-chat"
        self._tracer = get_tracer(f"swarm-{self.__class__.__name__.lower()}")

    @property
    @abstractmethod
    def name(self) -> str:
        """Возвращает имя агента."""
        ...

    @property
    def llm_provider(self) -> BaseLLMProvider:
        """Возвращает провайдер LLM."""
        return self._llm_provider

    @property
    def model_name(self) -> str:
        """Возвращает имя модели."""
        return self._model_name

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Возвращает системный промпт агента."""
        ...

    @abstractmethod
    async def process(self, state: SwarmState) -> dict[str, Any]:
        """Обрабатывает текущее состояние и возвращает обновление.

        Args:
            state: текущее состояние графа

        Returns:
            dict[str, Any]: словарь с обновлёнными полями состояния
        """
        ...

    async def _call_llm(self, messages: list[dict[str, str]]) -> str:
        """Вызывает LLM через абстрактный провайдер.

        Аргументы:
            messages: список сообщений для отправки в LLM

        Returns:
            str: текстовый ответ модели или сообщение об ошибке (fallback)
        """
        span_name = f"{self.__class__.__name__}._call_llm"

        if self._tracer is not None:
            with self._tracer.start_as_current_span(
                span_name,
                attributes={
                    "agent.model": self._model_name,
                    "agent.messages_count": len(messages),
                },
            ) as span:
                try:
                    return await self._do_call_llm(messages, span)
                except Exception as e:
                    error_msg = f"{self.name} LLM call failed: {e}"
                    logger.error(error_msg)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    return f"ERROR: {e}"
        else:
            try:
                return await self._do_call_llm(messages, None)
            except Exception as e:
                error_msg = f"{self.name} LLM call failed: {e}"
                logger.error(error_msg)
                return f"ERROR: {e}"

    async def _do_call_llm(self, messages: list[dict[str, str]], span=None) -> str:
        """Внутренний метод вызова LLM с опциональным span."""
        try:
            # Добавляем system prompt первым сообщением
            full_messages = [
                {"role": "system", "content": self.system_prompt},
                *messages,
            ]

            response: LLMResponse = await self._llm_provider.generate(
                messages=full_messages,
                model=self._model_name,
                temperature=0.7,
            )

            if span is not None:
                span.set_attribute("llm.success", True)

            return response.content

        except Exception as e:
            error_msg = f"Ошибка при вызове LLM ({self.name}): {e}"
            logger.error(error_msg)

            if span is not None:
                span.set_attribute("llm.success", False)
                span.set_attribute("llm.error", str(e))
                span.record_exception(e)

            raise
