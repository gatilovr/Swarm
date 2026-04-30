"""Главный модуль для запуска роя AI-агентов."""

import asyncio
import os
from typing import Any, AsyncGenerator

from swarm.config import SwarmConfig
from swarm.graph.workflow import create_swarm_graph
from swarm.state import SwarmState
from swarm.tracing import get_tracer


class SwarmRunner:
    """Запускает рой AI-агентов для выполнения задачи.

    Пример использования:
        runner = SwarmRunner()
        result = await runner.run("Напиши функцию на Python для сортировки")
        print(result["code"])
    """

    def __init__(self, config: SwarmConfig | None = None) -> None:
        """Инициализирует SwarmRunner.

        Args:
            config: конфигурация роя (если None, загружается из .env)
        """
        self.config = config or SwarmConfig.from_env()
        self.app = create_swarm_graph(self.config)
        self._last_result: dict[str, Any] = {}
        self._tracer = get_tracer("swarm-runner")

    async def run(self, task: str, thread_id: str = "default") -> dict[str, Any]:
        """Запускает рой агентов для выполнения задачи.

        Args:
            task: текстовая задача для выполнения
            thread_id: идентификатор потока для сохранения состояния

        Returns:
            dict[str, Any]: финальное состояние графа с результатами
        """
        span_name = "swarm.run"
        if self._tracer is not None:
            with self._tracer.start_as_current_span(
                span_name,
                attributes={
                    "swarm.task": task[:200],
                    "swarm.thread_id": thread_id,
                    "swarm.max_iterations": self.config.max_iterations,
                },
            ) as span:
                result = await self._do_run(task, thread_id)
                span.set_attribute("swarm.iterations", result.get("iteration", 0))
                span.set_attribute("swarm.approved", "APPROVED" in result.get("review_result", ""))
                span.set_attribute("swarm.plan_length", len(result.get("plan", "")))
                span.set_attribute("swarm.code_length", len(result.get("code", "")))
                return result
        else:
            return await self._do_run(task, thread_id)

    async def _do_run(self, task: str, thread_id: str = "default") -> dict[str, Any]:
        """Внутренний метод run без трассировки."""
        initial_state: SwarmState = {
            "messages": [],
            "task": task,
            "plan": "",
            "code": "",
            "review_result": "",
            "iteration": 0,
            "max_iterations": self.config.max_iterations,
            "is_final": False,
        }

        config = {"configurable": {"thread_id": thread_id}}

        final_state = await self.app.ainvoke(initial_state, config=config)
        self._last_result = final_state
        return final_state

    async def stream(
        self,
        task: str,
        thread_id: str = "default",
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Запускает рой с пошаговым выводом для отслеживания процесса.

        Args:
            task: текстовая задача для выполнения
            thread_id: идентификатор потока для сохранения состояния

        Yields:
            dict[str, Any]: словарь с информацией о текущем шаге

        Returns:
            dict[str, Any]: финальное состояние графа
        """
        span_name = "swarm.stream"
        if self._tracer is not None:
            with self._tracer.start_as_current_span(
                span_name,
                attributes={
                    "swarm.task": task[:200],
                    "swarm.thread_id": thread_id,
                },
            ) as span:
                async for info in self._do_stream(task, thread_id, span):
                    yield info
        else:
            async for info in self._do_stream(task, thread_id, None):
                yield info

    async def _do_stream(
        self,
        task: str,
        thread_id: str = "default",
        span=None,
    ) -> AsyncGenerator[dict[str, Any], None]:
        """Внутренний метод stream без/с трассировкой."""
        initial_state: SwarmState = {
            "messages": [],
            "task": task,
            "plan": "",
            "code": "",
            "review_result": "",
            "iteration": 0,
            "max_iterations": self.config.max_iterations,
            "is_final": False,
        }

        config = {"configurable": {"thread_id": thread_id}}

        iteration_count = 0
        last_event = None

        async for event in self.app.astream(initial_state, config=config):
            last_event = event
            for node_name, node_output in event.items():
                info: dict[str, Any] = {"node": node_name, "output": node_output}

                if node_name == "architect":
                    info["emoji"] = "ARCH"
                    info["label"] = "Архитектор"
                    if span is not None:
                        span.add_event("agent_iteration", {
                            "iteration": iteration_count,
                            "agent": "architect",
                        })
                    print(f"\n{'='*60}")
                    print(f"  [ARCH] АРХИТЕКТОР (планирование)")
                    print(f"{'='*60}")
                    if "plan" in node_output:
                        print(node_output["plan"])
                        print()

                elif node_name == "coder":
                    info["emoji"] = "CODE"
                    info["label"] = "Кодер"
                    iteration_count += 1
                    if span is not None:
                        span.add_event("agent_iteration", {
                            "iteration": iteration_count,
                            "agent": "coder",
                        })
                    print(f"\n{'='*60}")
                    print(f"  [CODE] КОДЕР (итерация {iteration_count})")
                    print(f"{'='*60}")
                    if "code" in node_output:
                        print(node_output["code"])
                        print()

                elif node_name == "reviewer":
                    info["emoji"] = "REVW"
                    info["label"] = "Ревьюер"
                    if span is not None:
                        span.add_event("agent_iteration", {
                            "iteration": iteration_count,
                            "agent": "reviewer",
                        })
                    print(f"\n{'='*60}")
                    print(f"  [REVW] РЕВЬЮЕР (проверка)")
                    print(f"{'='*60}")
                    if "review_result" in node_output:
                        result = node_output["review_result"]
                        is_approved = "APPROVED" in result.upper()
                        status = "[OK] ПРИНЯТО" if is_approved else "[FAIL] ОТКЛОНЕНО"
                        print(f"  Статус: {status}")
                        print(result)
                        print()

                yield info

        # После завершения stream получаем финальное состояние
        try:
            current_state = self.app.get_state(config)
            if current_state is not None and current_state.values:
                final_state = dict(current_state.values)
            else:
                # Собираем последний event
                final_state = {}
                if last_event:
                    for node_output in last_event.values():
                        if isinstance(node_output, dict):
                            final_state.update(node_output)
        except Exception:
            final_state = {}

        if span is not None:
            span.set_attribute("swarm.total_iterations", iteration_count)

        self._last_result = final_state


async def main() -> None:
    """Точка входа: загружает конфиг, запрашивает задачу и запускает рой."""
    print("=" * 60)
    print("  [AI] РОЙ AI-АГЕНТОВ")
    print("  Архитектор -> Кодер -> Ревьюер (с циклом доработки)")
    print("=" * 60)

    # Загрузка конфигурации
    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
    config = SwarmConfig.from_env(env_path)

    if not config.deepseek_api_key:
        print("\n⚠️  ВНИМАНИЕ: DEEPSEEK_API_KEY не найден в .env файле!")
        print("   Создайте файл .env на основе .env.example и укажите ваш API-ключ.\n")
        api_key = input("  Введите API-ключ DeepSeek (или нажмите Enter для выхода): ").strip()
        if not api_key:
            print("  Выход.")
            return
        config.deepseek_api_key = api_key

    print(f"\n  Модель архитектора: {config.architect_model_name}")
    print(f"  Модель кодера: {config.coder_model_name}")
    print(f"  Модель ревьюера: {config.reviewer_model_name}")
    print(f"  Максимум итераций: {config.max_iterations}")
    print()

    # Запрос задачи
    print("  Введите задачу для роя AI-агентов (или 'exit' для выхода):")
    print("  Пример: Напиши функцию на Python для быстрой сортировки (quicksort)")
    task = input("  > ").strip()

    if not task or task.lower() == "exit":
        print("  Выход.")
        return

    # Запуск роя
    runner = SwarmRunner(config=config)

    try:
        # Пошаговый вывод (stream сам собирает финальное состояние)
        async for _ in runner.stream(task):
            pass

        # Финальное состояние уже сохранено в _last_result после stream()
        final = runner._last_result
        print("\n" + "=" * 60)
        print("  ✅ РЕЗУЛЬТАТ ВЫПОЛНЕНИЯ")
        print("=" * 60)
        print(f"\n  📋 План архитектора:\n{final.get('plan', 'Нет плана')}\n")
        print(f"  💻 Код:\n{final.get('code', 'Нет кода')}\n")
        print(f"  🔍 Результат ревью: {final.get('review_result', 'Нет ревью')}\n")

    except Exception as e:
        print(f"\n❌ Ошибка при выполнении: {e}")


if __name__ == "__main__":
    asyncio.run(main())
