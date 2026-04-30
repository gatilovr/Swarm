"""Агент-кодер: пишет код по плану архитектора."""

from typing import Any

from swarm.agents.base import BaseAgent
from swarm.state import SwarmState


class CoderAgent(BaseAgent):
    """Агент-кодер, реализующий код по плану архитектора."""

    @property
    def name(self) -> str:
        return "Coder"

    @property
    def system_prompt(self) -> str:
        return (
            "Ты — опытный Разработчик (Кодер). Твоя задача — писать чистый, рабочий код "
            "строго по плану, который предоставил Архитектор.\n\n"
            "Правила:\n"
            "1. Следуй плану Архитектора шаг за шагом\n"
            "2. Пиши полностью рабочий код с комментариями на русском\n"
            "3. Используй лучшие практики и паттерны проектирования\n"
            "4. Добавляй обработку ошибок где необходимо\n"
            "5. Код должен быть готов к запуску\n\n"
            "Если что-то в плане неясно — напиши об этом и предложи свой вариант."
        )

    async def process(self, state: SwarmState) -> dict[str, Any]:
        """Пишет код на основе плана архитектора.

        Args:
            state: текущее состояние графа

        Returns:
            dict[str, Any]: обновление с полем code
        """
        plan = state.get("plan", "План не предоставлен.")
        task = state.get("task", "")
        review_feedback = state.get("review_result", "")

        prompt_parts = [
            f"Исходная задача: {task}",
            f"План архитектора: {plan}",
        ]

        if review_feedback and "REJECTED" in review_feedback:
            prompt_parts.append(f"Замечания ревьюера (доработай с учётом этих замечаний): {review_feedback}")

        prompt_parts.append("\nНапиши полный, рабочий код в соответствии с планом.")

        messages = [
            {"role": "user", "content": "\n\n".join(prompt_parts)}
        ]
        response_text = await self._call_llm(messages)

        # Инкрементируем счётчик итераций при каждом проходе кодера
        current_iteration = state.get("iteration", 0)

        return {"code": response_text, "iteration": current_iteration + 1}
