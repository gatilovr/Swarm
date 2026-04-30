"""Mock-тест для Swarm роя AI-агентов.

Заменяет BaseLLMProvider на mock с предопределёнными ответами,
чтобы проверить корректность работы графа без реального API.
"""

import sys
from pathlib import Path

# Добавляем корень проекта в sys.path для импорта пакета swarm
_project_root = str(Path(__file__).parent.parent.parent)
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from unittest.mock import patch, MagicMock, AsyncMock

import pytest

from swarm import SwarmRunner
from swarm.config import SwarmConfig


@pytest.fixture
def mock_llm_provider():
    """Создаёт mock для BaseLLMProvider с предопределёнными ответами."""
    # Предопределённые ответы для каждого агента
    mock_responses = {
        "architect": "План: 1. Создать функцию 2. Добавить комментарии",
        "coder": "def hello():\n    print('Hello, World!')",
        "reviewer": "APPROVED. Код соответствует плану.",
    }

    response_order = [
        mock_responses["architect"],
        mock_responses["coder"],
        mock_responses["reviewer"],
    ]

    response_index = [0]

    async def generate_side_effect(messages, model=None, temperature=0.7, max_tokens=None):
        """Возвращает предопределённые ответы по порядку."""
        idx = response_index[0]
        response_index[0] += 1
        text = response_order[idx]

        mock_response = MagicMock()
        mock_response.content = text
        mock_response.model = model or "deepseek-chat"
        mock_response.provider = "test"
        mock_response.prompt_tokens = 10
        mock_response.completion_tokens = 20
        mock_response.total_tokens = 30
        mock_response.latency_seconds = 0.1
        return mock_response

    mock_provider = MagicMock(spec=[])

    # Настраиваем async метод generate
    mock_provider.generate = AsyncMock(side_effect=generate_side_effect)

    # Настраиваем count_tokens
    mock_provider.count_tokens = MagicMock(return_value=100)

    # Настраиваем provider_name
    mock_provider.provider_name = "test"

    return mock_provider, response_index


def test_swarm_graph_mock():
    """Проверяет, что граф проходит все узлы: architect -> coder -> reviewer -> END."""

    with patch("swarm.config.LiteLLMProvider") as mock_provider_cls:
        # Настраиваем mock для провайдера
        mock_instance = MagicMock()

        async def generate_side_effect(messages, model=None, temperature=0.7, max_tokens=None):
            idx = generate_side_effect.call_count
            generate_side_effect.call_count += 1

            mock_responses = [
                "План: 1. Создать функцию 2. Добавить комментарии",
                "def hello():\n    print('Hello, World!')",
                "APPROVED. Код соответствует плану.",
            ]

            text = mock_responses[idx] if idx < len(mock_responses) else ""

            mock_response = MagicMock()
            mock_response.content = text
            mock_response.model = model or "deepseek-chat"
            mock_response.provider = "test"
            mock_response.prompt_tokens = 10
            mock_response.completion_tokens = 20
            mock_response.total_tokens = 30
            mock_response.latency_seconds = 0.1
            return mock_response

        generate_side_effect.call_count = 0
        mock_instance.generate = AsyncMock(side_effect=generate_side_effect)
        mock_instance.count_tokens = MagicMock(return_value=100)
        mock_instance.provider_name = "test"

        # LiteLLMProvider.from_config() возвращает наш mock
        mock_provider_cls.from_config = MagicMock(return_value=mock_instance)
        mock_provider_cls.return_value = mock_instance

        # Создаём конфиг с mock-ключом
        config = SwarmConfig(deepseek_api_key="mock_key")
        runner = SwarmRunner(config=config)

        # === TEST 1: run() — обычный режим ===
        print("=" * 60)
        print("  TEST 1: run() — normal mode")
        print("=" * 60)

        import asyncio
        result = asyncio.run(runner.run("Напиши функцию hello"))

        # Проверка: generate вызван 3 раза (architect, coder, reviewer)
        assert mock_instance.generate.call_count == 3, (
            f"Expected 3 generate calls, got {mock_instance.generate.call_count}"
        )
        print("  [PASS] generate called 3 times (1 per agent)")

        # Проверка: Архитектор создал план
        plan = result.get("plan", "")
        assert "План" in plan, "Plan missing expected text"
        assert "1. Создать функцию" in plan, "Plan missing steps"
        print(f"  [PASS] Architect created plan: {plan[:60]}...")

        # Проверка: Кодер написал код
        code = result.get("code", "")
        assert "def hello()" in code, "Code missing hello function"
        print(f"  [PASS] Coder wrote code: {code[:60]}...")

        # Проверка: Ревьюер одобрил код
        review = result.get("review_result", "")
        assert "APPROVED" in review.upper(), "Reviewer did not approve"
        print(f"  [PASS] Reviewer approved: {review[:60]}...")

        # Проверка графа: завершился APPROVED
        assert "APPROVED" in result.get("review_result", "").upper(), "Graph did not end with APPROVED"
        print("  [PASS] Graph terminated with APPROVED")

        print(f"\n  State summary:")
        print(f"    Plan: {plan}")
        print(f"    Code: {code}")
        print(f"    Review: {review}")

        # === TEST 2: stream() — пошаговый режим ===
        print(f"\n{'=' * 60}")
        print("  TEST 2: stream() — step-by-step mode")
        print(f"{'=' * 60}")

        # Сброс счётчика для stream
        generate_side_effect.call_count = 0

        async def run_stream():
            node_order = []
            async for step in runner.stream("Напиши функцию hello"):
                node_order.append(step.get("node"))
                label = step.get("label", "")
                print(f"  Node: {label}")
            return node_order

        node_order = asyncio.run(run_stream())

        # Проверка порядка узлов в stream
        expected_order = ["architect", "coder", "reviewer"]
        assert node_order == expected_order, (
            f"Wrong node order: {node_order}, expected: {expected_order}"
        )
        print("  [PASS] Stream node order: architect -> coder -> reviewer")
        print("  [PASS] Stream mode works correctly")

        print(f"\n{'=' * 60}")
        print("  ALL TESTS PASSED")
        print(f"{'=' * 60}")


def test_swarm_graph_rejected_cycle():
    """Проверяет цикл REJECTED → coder → reviewer → APPROVED."""

    with patch("swarm.config.LiteLLMProvider") as mock_provider_cls:
        mock_instance = MagicMock()

        mock_responses = [
            "План: 1. Создать функцию 2. Добавить комментарии",
            "def hello():\n    print('Hello')",
            "REJECTED. Нет обработки ошибок. Добавьте try-except.",
            "def hello():\n    try:\n        print('Hello')\n    except Exception as e:\n        print(f'Error: {e}')",
            "APPROVED. Код соответствует плану, обработка ошибок добавлена.",
        ]

        response_index = [0]

        async def generate_side_effect(messages, model=None, temperature=0.7, max_tokens=None):
            idx = response_index[0]
            response_index[0] += 1
            text = mock_responses[idx] if idx < len(mock_responses) else ""

            mock_response = MagicMock()
            mock_response.content = text
            mock_response.model = model or "deepseek-chat"
            mock_response.provider = "test"
            mock_response.prompt_tokens = 10
            mock_response.completion_tokens = 20
            mock_response.total_tokens = 30
            mock_response.latency_seconds = 0.1
            return mock_response

        mock_instance.generate = AsyncMock(side_effect=generate_side_effect)
        mock_instance.count_tokens = MagicMock(return_value=100)
        mock_instance.provider_name = "test"

        mock_provider_cls.from_config = MagicMock(return_value=mock_instance)
        mock_provider_cls.return_value = mock_instance

        config = SwarmConfig(deepseek_api_key="mock_key")
        runner = SwarmRunner(config=config)

        import asyncio
        result = asyncio.run(runner.run("Напиши функцию hello с обработкой ошибок"))

        # Диагностика
        print(f"  DEBUG: result keys: {result.keys()}")
        print(f"  DEBUG: review_result: {result.get('review_result')}")
        print(f"  DEBUG: iteration: {result.get('iteration')}")
        print(f"  DEBUG: generate.call_count: {mock_instance.generate.call_count}")

        # generate вызывается 5 раз: architect + coder1 + reviewer1 + coder2 + reviewer2
        assert mock_instance.generate.call_count == 5, (
            f"Expected 5 LLM generate calls, got {mock_instance.generate.call_count}"
        )
        print("  [PASS] LLM generate called 5 times (architect + 2 coder + 2 reviewer)")

        # Проверка: финальный код — вторая версия
        code = result.get("code", "")
        assert "try" in code, "Final code missing try-except"
        print("  [PASS] Final code includes try-except from second iteration")

        # Проверка: финальный результат — APPROVED
        review = result.get("review_result", "")
        assert "APPROVED" in review.upper(), "Reviewer did not approve on second pass"
        print("  [PASS] Reviewer approved after revision")

        # Проверка: итерация = 2
        iteration = result.get("iteration", 0)
        assert iteration == 2, f"Expected iteration=2, got {iteration}"
        print(f"  [PASS] Correct iteration count: {iteration}")

        print(f"\n  State summary:")
        print(f"    Code: {code[:60]}...")
        print(f"    Review: {review[:60]}...")
        print(f"    Iteration: {iteration}")


if __name__ == "__main__":
    result = test_swarm_graph_mock()
    test_swarm_graph_rejected_cycle()
