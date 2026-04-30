"""Агент-ревьюер: проверяет код на соответствие плану."""

from typing import Any

from swarm.agents.base import BaseAgent
from swarm.state import SwarmState


class ReviewerAgent(BaseAgent):
    """Агент-ревьюер, проверяющий код на соответствие плану и качество."""

    @property
    def name(self) -> str:
        return "Reviewer"

    @property
    def system_prompt(self) -> str:
        return (
            "Ты — строгий Ревьюер кода. Твоя задача — проверить код разработчика на:\n\n"
            "1. Соответствие плану Архитектора\n"
            "2. Корректность и работоспособность\n"
            "3. Соблюдение лучших практик\n"
            "4. Полноту реализации\n"
            "5. Обработку ошибок\n"
            "6. Чистоту и читаемость кода\n\n"
            "Отвечай ТОЛЬКО одним из двух вариантов:\n"
            "- APPROVED: если код полностью соответствует плану и готов к использованию\n"
            "- REJECTED: если есть замечания. После REJECTED напиши конкретные замечания и что нужно исправить.\n\n"
            "Будь максимально строгим и объективным."
        )

    async def process(self, state: SwarmState) -> dict[str, Any]:
        """Проверяет код на соответствие плану.

        Args:
            state: текущее состояние графа

        Returns:
            dict[str, Any]: обновление с полем review_result
        """
        plan = state.get("plan", "План не предоставлен.")
        code = state.get("code", "Код не предоставлен.")
        iteration = state.get("iteration", 0)
        max_iterations = state.get("max_iterations", 3)

        messages = [
            {
                "role": "user",
                "content": (
                    f"План Архитектора:\n{plan}\n\n"
                    f"Код Разработчика:\n{code}\n\n"
                    f"Итерация: {iteration + 1} из {max_iterations}\n\n"
                    "Проверь код на соответствие плану. Отвечай только APPROVED или REJECTED."
                ),
            }
        ]
        response_text = await self._call_llm(messages)

        return {"review_result": response_text}
