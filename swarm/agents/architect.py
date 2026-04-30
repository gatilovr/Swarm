"""Агент-архитектор: создаёт план реализации."""

from typing import Any

from swarm.agents.base import BaseAgent
from swarm.state import SwarmState


class ArchitectAgent(BaseAgent):
    """Агент-архитектор, анализирующий задачу и создающий план реализации."""

    @property
    def name(self) -> str:
        return "Architect"

    @property
    def system_prompt(self) -> str:
        return (
            "Ты — опытный Архитектор ПО. Твоя задача — проанализировать запрос пользователя и создать "
            "детальный, пошаговый план реализации кода. План должен включать:\n\n"
            "1. Анализ требований и описание задачи\n"
            "2. Выбор архитектуры и технологий\n"
            "3. Структуру компонентов и их взаимодействие\n"
            "4. Детальный план реализации (файлы, функции, классы)\n"
            "5. Рекомендации по тестированию\n\n"
            "ВАЖНО: Не пиши сам код реализации! Только план и архитектуру.\n"
            "Будь конкретным и практичным. Используй понятные формулировки."
        )

    async def process(self, state: SwarmState) -> dict[str, Any]:
        """Обрабатывает задачу и создаёт план.

        Args:
            state: текущее состояние графа

        Returns:
            dict[str, Any]: обновление с полем plan
        """
        messages = [
            {"role": "user", "content": f"Проанализируй следующую задачу и создай план реализации:\n\n{state['task']}"}
        ]
        response_text = await self._call_llm(messages)

        return {"plan": response_text}
