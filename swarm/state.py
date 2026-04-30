"""Определение состояния графа Swarm."""

from typing import Annotated, TypedDict

from langgraph.graph.message import add_messages


class SwarmState(TypedDict):
    """Состояние графа роя AI-агентов.

    Поля:
        messages: история сообщений между агентами
        task: исходная задача пользователя
        plan: план, созданный архитектором
        code: код, написанный кодером
        review_result: результат ревью (APPROVED/REJECTED)
        iteration: номер текущей итерации
        max_iterations: максимальное количество итераций
        is_final: флаг финального ответа
    """

    messages: Annotated[list, add_messages]
    task: str
    plan: str
    code: str
    review_result: str
    iteration: int
    max_iterations: int
    is_final: bool
