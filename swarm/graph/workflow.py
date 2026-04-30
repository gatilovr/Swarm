"""Построение графа LangGraph для роя AI-агентов."""

from typing import Literal

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from swarm.agents.architect import ArchitectAgent
from swarm.agents.coder import CoderAgent
from swarm.agents.reviewer import ReviewerAgent
from swarm.config import SwarmConfig
from swarm.state import SwarmState


def create_swarm_graph(config: SwarmConfig) -> CompiledStateGraph:
    """Создаёт и компилирует граф LangGraph для роя AI-агентов.

    Граф состоит из трёх узлов:
        - architect: создаёт план
        - coder: пишет код
        - reviewer: проверяет код

    После проверки граф либо завершается (APPROVED),
        либо возвращает кодера на доработку (REJECTED).

    LangGraph поддерживает async функции в качестве узлов графа
    (начиная с версии >= 0.2.0). При вызове invoke()/ainvoke()
    async-узлы выполняются корректно.

    Args:
        config: конфигурация роя

    Returns:
        CompiledStateGraph: скомпилированный граф
    """
    # Инициализация агентов с провайдером LLM
    architect_agent = ArchitectAgent(
        llm_provider=config.get_architect_llm(),
        model_name=config.architect_model_name,
    )
    coder_agent = CoderAgent(
        llm_provider=config.get_coder_llm(),
        model_name=config.coder_model_name,
    )
    reviewer_agent = ReviewerAgent(
        llm_provider=config.get_reviewer_llm(),
        model_name=config.reviewer_model_name,
    )

    # Создание графа
    workflow = StateGraph(SwarmState)

    # Добавление узлов с async-функциями
    # LangGraph >= 0.2.0 поддерживает async функции в узлах
    workflow.add_node("architect", architect_agent.process)
    workflow.add_node("coder", coder_agent.process)
    workflow.add_node("reviewer", reviewer_agent.process)

    def router(state: SwarmState) -> Literal["coder", "__end__"]:
        """Определяет следующий шаг на основе результата ревью.

        Args:
            state: текущее состояние графа

        Returns:
            str: имя следующего узла или END
        """
        review_result = state.get("review_result", "")
        iteration = state.get("iteration", 0)
        max_iterations = state.get("max_iterations", 3)

        if "APPROVED" in review_result.upper():
            return END
        if iteration >= max_iterations:
            return END
        return "coder"

    # Настройка рёбер
    workflow.set_entry_point("architect")
    workflow.add_edge("architect", "coder")
    workflow.add_edge("coder", "reviewer")
    workflow.add_conditional_edges(
        "reviewer",
        router,
        {
            "coder": "coder",
            END: END,
        },
    )

    # Компиляция с памятью
    memory = MemorySaver()
    app = workflow.compile(checkpointer=memory)

    return app
