"""
MCP-сервер для роя AI-агентов.

Предоставляет инструмент `run_swarm`, который запускает
Architect -> Coder -> Reviewer для генерации кода по ТЗ.

Использование:
    python -m swarm_mcp

Поддерживает опциональный режим с SwarmWorker (кэш + rate limiter)
при установке MCP_USE_WORKER=true.
"""

import asyncio
import logging
import os
import sys
from typing import Any, Optional

# Добавляем путь к корню проекта для импорта swarm
# server.py находится в swarm-mcp/src/swarm_mcp/server.py
# Нам нужно подняться на 3 уровня вверх, чтобы получить c:/Users/gatil/VisualStudioCodeProject/Swarm
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..")
)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp.server import Server, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool as MCPTool,
    TextContent,
    ProgressNotification,
    ProgressNotificationParams,
)
from swarm import SwarmRunner, SwarmConfig

from .config import MCPConfig

logger = logging.getLogger("swarm-mcp")


def create_server(config: Optional[MCPConfig] = None) -> Server:
    """Создаёт и настраивает MCP-сервер.

    Args:
        config: конфигурация MCP-сервера (если None, загружается из .env).

    Returns:
        Server: настроенный экземпляр MCP-сервера.
    """
    cfg = config or MCPConfig()
    server = Server(cfg.server_name)

    # ------------------------------------------------------------------ #
    # list_tools
    # ------------------------------------------------------------------ #
    @server.list_tools()
    async def list_tools() -> list[MCPTool]:
        """Возвращает список доступных инструментов."""
        return [
            MCPTool(
                name="run_swarm",
                description=(
                    "Запускает команду AI-агентов (Архитектор -> Кодер -> Ревьюер) "
                    "для написания кода по вашему техническому заданию.\n\n"
                    "Агенты работают в цикле:\n"
                    "1. Архитектор — анализирует ТЗ и создаёт план\n"
                    "2. Кодер — пишет код по плану\n"
                    "3. Ревьюер — проверяет код (APPROVED/REJECTED)\n\n"
                    "При REJECTED код отправляется на доработку (до 3 итераций)."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Детальное техническое задание на разработку",
                        },
                        "complexity": {
                            "type": "string",
                            "description": "Подсказка сложности: auto | low | medium | high | critical. По умолчанию auto — ModelSelector определит сам",
                            "enum": ["auto", "low", "medium", "high", "critical"],
                        },
                        "project_files": {
                            "type": "integer",
                            "description": "Примерное количество файлов в проекте. Swarm учтёт это при выборе стратегии",
                        },
                    },
                    "required": ["task"],
                },
            )
        ]

    # ------------------------------------------------------------------ #
    # call_tool
    # ------------------------------------------------------------------ #
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Обрабатывает вызов инструмента."""
        if name != "run_swarm":
            raise ValueError(f"Unknown tool: {name}")

        task_text = arguments.get("task", "")
        if not task_text:
            return [
                TextContent(
                    type="text",
                    text="ERROR: Parameter 'task' is required.",
                )
            ]

        # Извлекаем опциональные поля
        complexity = arguments.get("complexity", "auto")
        project_files = arguments.get("project_files", 0)

        # Проверка API-ключа
        if not cfg.swarm.deepseek_api_key:
            return [
                TextContent(
                    type="text",
                    text=(
                        "ERROR: DEEPSEEK_API_KEY not configured.\n\n"
                        "Create a .env file in the project root with:\n"
                        "DEEPSEEK_API_KEY=your_api_key_here\n\n"
                        "See README.md for details."
                    ),
                )
            ]

        try:
            if cfg.use_worker:
                # ---- Режим с SwarmWorker (кэш + rate limiter) ----
                result_text = await _run_with_worker(cfg, task_text, complexity, project_files)
            else:
                # ---- Режим с прямым SwarmRunner ----
                result_text = await _run_with_runner(cfg, task_text)

            return [TextContent(type="text", text=result_text)]

        except Exception as e:
            logger.exception("Error running swarm")
            return [
                TextContent(
                    type="text",
                    text=f"ERROR: {e}",
                )
            ]

    return server


async def _run_with_runner(cfg: MCPConfig, task_text: str) -> str:
    """Запускает рой через прямой SwarmRunner.

    Args:
        cfg: конфигурация MCP-сервера
        task_text: текст задачи

    Returns:
        str: отформатированный результат
    """
    runner = SwarmRunner(cfg.swarm)

    # Запускаем и собираем все шаги (теперь stream — async generator)
    final_state: dict[str, Any] = {}
    async for step in runner.stream(task_text):
        # Сохраняем финальное состояние на каждом шаге
        if runner._last_result:
            final_state = runner._last_result

    return _format_output(
        plan=final_state.get("plan"),
        code=final_state.get("code"),
        review=final_state.get("review_result"),
    )


async def _run_with_worker(cfg: MCPConfig, task_text: str, complexity: str = "auto", project_files: int = 0) -> str:
    """Запускает рой через SwarmWorker (с кэшем и rate limiter).

    Args:
        cfg: конфигурация MCP-сервера
        task_text: текст задачи
        complexity: подсказка сложности (auto/low/medium/high/critical)
        project_files: количество файлов в проекте

    Returns:
        str: отформатированный результат
    """
    import uuid

    # Lazy import — swarm-scale опциональная зависимость
    from swarm_scale import SwarmWorker, ScaleConfig
    from swarm_scale.task import Task as ScaleTask

    scale_config = ScaleConfig()
    worker = SwarmWorker(scale_config)

    scale_task = ScaleTask(
        task_id=f"mcp-{uuid.uuid4().hex[:8]}",
        content=task_text,
        repository="mcp-client",
        file_path="unknown",
        complexity_hint=complexity,
        project_files=project_files,
    )

    result = await worker.process_task(scale_task)

    if result.error:
        return f"ERROR: {result.error}"

    return _format_output(
        plan=result.plan,
        code=result.code,
        review=result.review_result,
        cached=result.cached,
    )


def _format_output(plan: str, code: str, review: str, cached: bool = False) -> str:
    """Форматирует результат работы роя в читаемый текст.

    Args:
        plan: план архитектора
        code: итоговый код
        review: результат ревью
        cached: флаг, указывающий что результат из кэша

    Returns:
        str: отформатированный результат
    """
    parts: list[str] = []
    if cached:
        parts.append("⚡ Результат из кэша")
        parts.append("")
    if plan:
        parts.append("## 🏗️ План архитектора")
        parts.append("")
        parts.append(plan)
    if code:
        parts.append("---")
        parts.append("")
        parts.append("## 💻 Итоговый код")
        parts.append("")
        parts.append("```python")
        parts.append(code)
        parts.append("```")
    if review:
        parts.append("---")
        parts.append("")
        parts.append("## 🔍 Результат ревью")
        parts.append("")
        parts.append(review)
    return "\n".join(parts) if parts else "Рой не вернул результат."


async def main() -> None:
    """Точка входа. Запускает MCP-сервер через stdio."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting swarm-mcp server...")

    config = MCPConfig()
    if config.use_worker:
        logger.info("SwarmWorker mode enabled (caching + rate limiter active)")

    server = create_server(config)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(
                notification_options=NotificationOptions(
                    prompts_changed=False,
                    resources_changed=False,
                    tools_changed=False,
                )
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
