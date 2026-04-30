"""
MCP-сервер Swarm — продуктовый AI-агент для полной разработки проекта.

Предоставляет высокоуровневые инструменты:
- run_swarm:  запуск полного цикла разработки (Architect -> Coder -> Reviewer)
- swarm_status: состояние проекта
- swarm_ask:    вопросы по проекту
- swarm_execute: безопасное выполнение команд
- swarm_files:  чтение файлов проекта

Использование:
    python -m swarm_mcp
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from importlib.metadata import distribution, PackageNotFoundError
from typing import Any, Optional

# Добавляем путь к корню проекта для импорта swarm
# Сначала пытаемся найти swarm через importlib.metadata,
# иначе fallback на путь относительно server.py
try:
    dist = distribution("swarm")
    _PROJECT_ROOT = str(dist.locate_file("."))
except (PackageNotFoundError, Exception):
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
)
from swarm import SwarmRunner, SwarmConfig

from .config import MCPConfig

logger = logging.getLogger("swarm-mcp")


# --------------------------------------------------------------------------- #
# Lazy-импорты для опциональных модулей
# --------------------------------------------------------------------------- #

def _get_status() -> Any:
    """Lazy import ProjectStatus."""
    from .status import ProjectStatus
    return ProjectStatus


def _get_ask() -> Any:
    """Lazy import ProjectQA."""
    from .ask import ProjectQA
    return ProjectQA


def _get_executor() -> Any:
    """Lazy import CommandExecutor."""
    from .executor import CommandExecutor
    return CommandExecutor


def _get_policy() -> Any:
    """Lazy import load_policy."""
    from .policy import load_policy
    return load_policy


# --------------------------------------------------------------------------- #
# Фабрика сервера
# --------------------------------------------------------------------------- #

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
        tools = [
            MCPTool(
                name="run_swarm",
                description=(
                    "Запускает команду AI-агентов (Архитектор -> Кодер -> Ревьюер) "
                    "для написания кода по вашему техническому заданию.\n\n"
                    "Агенты работают в цикле:\n"
                    "1. Архитектор — анализирует ТЗ и создаёт план\n"
                    "2. Кодер — пишет код по плану\n"
                    "3. Ревьюер — проверяет код (APPROVED/REJECTED)\n\n"
                    "При REJECTED код отправляется на доработку (до 3 итераций).\n\n"
                    "Возвращает JSON с результатами: план, код, ревью, "
                    "список созданных/изменённых файлов, статус тестов, "
                    "потраченные токены."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "task": {
                            "type": "string",
                            "description": "Детальное техническое задание на разработку",
                        },
                        "context": {
                            "type": "string",
                            "description": "Дополнительный контекст (файлы, архитектура, ограничения)",
                        },
                        "mode": {
                            "type": "string",
                            "description": "Режим: 'full' (по умолч.) — пишет код, 'plan' — только план без записи файлов",
                            "enum": ["full", "plan"],
                        },
                        "complexity": {
                            "type": "string",
                            "description": "Подсказка сложности: auto | low | medium | high | critical",
                            "enum": ["auto", "low", "medium", "high", "critical"],
                        },
                        "project_files": {
                            "type": "integer",
                            "description": "Примерное количество файлов в проекте",
                        },
                    },
                    "required": ["task"],
                },
            ),
            MCPTool(
                name="swarm_status",
                description=(
                    "Показывает состояние проекта: количество файлов, "
                    "статус тестов, git-статус, структуру директорий.\n\n"
                    "Полезно чтобы быстро оценить текущее состояние проекта "
                    "без запуска полного анализа."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "scope": {
                            "type": "string",
                            "description": "'summary' — кратко (по умолч.), 'full' — детально",
                            "enum": ["summary", "full"],
                        },
                    },
                    "required": [],
                },
            ),
            MCPTool(
                name="swarm_ask",
                description=(
                    "Задаёт вопрос о проекте и получает структурированный ответ "
                    "на основе анализа кода.\n\n"
                    "Поддерживаемые категории вопросов:\n"
                    "- Архитектура: 'какая архитектура?', 'как устроен проект?'\n"
                    "- Зависимости: 'какие библиотеки используются?'\n"
                    "- Безопасность: 'есть ли уязвимости?', 'как с аутентификацией?'\n"
                    "- Производительность: 'где узкое место?'\n"
                    "- Тесты: 'какие есть тесты?', 'какое покрытие?'\n"
                    "- Качество кода: 'как улучшить код?'\n"
                    "- Документация: 'есть ли документация?'\n"
                    "- Конфигурация: 'какие настройки?'\n"
                    "- Общие: 'что это за проект?'"
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": "Вопрос о проекте на естественном языке",
                        },
                        "files": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Ограничить анализ конкретными файлами (опционально)",
                        },
                    },
                    "required": ["question"],
                },
            ),
            MCPTool(
                name="swarm_execute",
                description=(
                    "Безопасно выполняет команду терминала с проверкой "
                    "по политикам .swarm-policy.toml.\n\n"
                    "Политика безопасности:\n"
                    "- auto_allow: команды выполняются без подтверждения "
                    "(pip install, pytest, git status)\n"
                    "- require_approval: требуется одобрение пользователя "
                    "(git push, rm -rf, sudo)\n"
                    "- deny: команды заблокированы полностью "
                    "(rm -rf /, chmod 777 /)\n\n"
                    "Если файл .swarm-policy.toml отсутствует, "
                    "используются политики по умолчанию."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string",
                            "description": "Команда для выполнения в терминале",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Таймаут в секундах (по умолч. из политики, макс 300)",
                        },
                        "approved": {
                            "type": "boolean",
                            "description": "Если true, команда считается предварительно одобренной",
                        },
                    },
                    "required": ["command"],
                },
            ),
            MCPTool(
                name="swarm_files",
                description=(
                    "Читает содержимое файлов проекта по glob-паттерну. "
                    "Полезно для получения информации о конкретных файлах "
                    "без чтения через Roo Code."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "pattern": {
                            "type": "string",
                            "description": "Glob-паттерн для поиска файлов (например, '**/*.py', 'src/**/*.ts')",
                        },
                        "max_lines": {
                            "type": "integer",
                            "description": "Максимальное строк на файл (по умолч. 100)",
                        },
                    },
                    "required": ["pattern"],
                },
            ),
        ]
        return tools

    # ------------------------------------------------------------------ #
    # call_tool
    # ------------------------------------------------------------------ #
    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        """Обрабатывает вызов инструмента."""
        handlers = {
            "run_swarm": _handle_run_swarm,
            "swarm_status": _handle_swarm_status,
            "swarm_ask": _handle_swarm_ask,
            "swarm_execute": _handle_swarm_execute,
            "swarm_files": _handle_swarm_files,
        }

        handler = handlers.get(name)
        if handler is None:
            return [TextContent(
                type="text",
                text=json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False),
                isError=True,
            )]

        try:
            result = await handler(cfg, arguments)
            return [TextContent(type="text", text=result)]
        except Exception as e:
            logger.exception("Error in tool %s", name)
            return [TextContent(
                type="text",
                text=json.dumps({"error": str(e)}, ensure_ascii=False),
                isError=True,
            )]

    return server


# --------------------------------------------------------------------------- #
# Handlers
# --------------------------------------------------------------------------- #

async def _handle_run_swarm(cfg: MCPConfig, args: dict) -> str:
    """Обрабатывает вызов run_swarm."""
    task_text = args.get("task", "")
    if not task_text:
        return json.dumps({"error": "Parameter 'task' is required."}, ensure_ascii=False)

    context = args.get("context", "")
    mode = args.get("mode", "full")
    complexity = args.get("complexity", "auto")
    project_files = args.get("project_files", 0)

    if not cfg.swarm.deepseek_api_key:
        return json.dumps({
            "error": "DEEPSEEK_API_KEY not configured. Create a .env file with DEEPSEEK_API_KEY=your_key",
        }, ensure_ascii=False)

    # Добавляем контекст к задаче если есть
    full_task = task_text
    if context:
        full_task = f"{task_text}\n\nКонтекст:\n{context}"

    if mode == "plan":
        # Режим "только план"
        return await _run_plan_only(cfg, full_task)

    if cfg.use_worker:
        result = await _run_with_worker(cfg, full_task, complexity, project_files)
    else:
        result = await _run_with_runner(cfg, full_task)

    return result


async def _handle_swarm_status(cfg: MCPConfig, args: dict) -> str:
    """Обрабатывает вызов swarm_status."""
    scope = args.get("scope", "summary")
    StatusClass = _get_status()
    analyzer = StatusClass(_PROJECT_ROOT)

    try:
        if scope == "full":
            data = analyzer.analyze()
        else:
            data = analyzer.summary()
        return json.dumps(data, ensure_ascii=False, default=str)
    except Exception as e:
        logger.exception("Error getting project status")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


async def _handle_swarm_ask(cfg: MCPConfig, args: dict) -> str:
    """Обрабатывает вызов swarm_ask."""
    question = args.get("question", "")
    if not question:
        return json.dumps({"error": "Parameter 'question' is required."}, ensure_ascii=False)

    files = args.get("files")
    QAClass = _get_ask()
    qa = QAClass(_PROJECT_ROOT)

    try:
        result = await qa.ask(question, files)
        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as e:
        logger.exception("Error answering question")
        return json.dumps({"error": str(e)}, ensure_ascii=False)


async def _handle_swarm_execute(cfg: MCPConfig, args: dict) -> str:
    """Обрабатывает вызов swarm_execute."""
    if not cfg.enable_executor:
        return json.dumps({
            "error": "Executor is disabled. Set MCP_ENABLE_EXECUTOR=true to enable.",
        }, ensure_ascii=False)

    command = args.get("command", "")
    if not command:
        return json.dumps({"error": "Parameter 'command' is required."}, ensure_ascii=False)

    timeout = args.get("timeout")
    approved = args.get("approved", False)

    ExecutorClass = _get_executor()
    executor = ExecutorClass()
    result = await executor.execute(command, timeout=timeout, approved=approved)

    return json.dumps({
        "command": result.command,
        "return_code": result.return_code,
        "stdout": result.stdout[:5000],  # Ограничение размера вывода
        "stderr": result.stderr[:2000],
        "duration_sec": round(result.duration_sec, 2),
        "classification": result.classification,
        "approved": result.approved,
        "error": result.error,
    }, ensure_ascii=False, default=str)


async def _handle_swarm_files(cfg: MCPConfig, args: dict) -> str:
    """Обрабатывает вызов swarm_files."""
    import fnmatch

    pattern = args.get("pattern", "")
    if not pattern:
        return json.dumps({"error": "Parameter 'pattern' is required."}, ensure_ascii=False)

    max_lines = args.get("max_lines", 100)

    results = []
    for dirpath, _, filenames in os.walk(_PROJECT_ROOT):
        # Исключаем скрытые и виртуальные
        if any(skip in dirpath for skip in (".git", "node_modules", "__pycache__", ".venv", ".hypothesis")):
            continue
        for fname in filenames:
            rel_path = os.path.relpath(os.path.join(dirpath, fname), _PROJECT_ROOT)
            if fnmatch.fnmatch(rel_path, pattern):
                try:
                    fpath = os.path.join(dirpath, fname)
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        lines = f.readlines()
                    content = "".join(lines[:max_lines])
                    truncated = len(lines) > max_lines
                    results.append({
                        "path": rel_path,
                        "lines": len(lines),
                        "content": content,
                        "truncated": truncated,
                    })
                except Exception as e:
                    results.append({
                        "path": rel_path,
                        "error": str(e),
                    })

    if not results:
        return json.dumps({
            "pattern": pattern,
            "files": [],
            "note": f"No files matching '{pattern}'",
        }, ensure_ascii=False)

    return json.dumps({
        "pattern": pattern,
        "files": results[:20],  # Ограничение на 20 файлов
        "total_found": len(results),
    }, ensure_ascii=False, default=str)


# --------------------------------------------------------------------------- #
# Внутренние функции run_swarm
# --------------------------------------------------------------------------- #

async def _run_plan_only(cfg: MCPConfig, task_text: str) -> str:
    """Режим 'только план' — возвращает план без записи кода.

    Args:
        cfg: конфигурация MCP-сервера
        task_text: текст задачи

    Returns:
        str: JSON с планом
    """
    runner = SwarmRunner(cfg.swarm)
    final_state: dict[str, Any] = {}

    async for step in runner.stream(task_text):
        if runner._last_result:
            final_state = runner._last_result

    return json.dumps({
        "status": "plan_ready",
        "mode": "plan",
        "plan": final_state.get("plan", ""),
        "review": final_state.get("review_result", ""),
        "note": "Режим 'plan' — код не был записан. Запустите с mode='full' для генерации кода.",
    }, ensure_ascii=False, default=str)


async def _run_with_runner(cfg: MCPConfig, task_text: str) -> str:
    """Запускает рой через прямой SwarmRunner.

    Args:
        cfg: конфигурация MCP-сервера
        task_text: текст задачи

    Returns:
        str: JSON с результатами
    """
    runner = SwarmRunner(cfg.swarm)

    final_state: dict[str, Any] = {}
    async for step in runner.stream(task_text):
        if runner._last_result:
            final_state = runner._last_result

    plan = final_state.get("plan", "")
    code = final_state.get("code", "")
    review = final_state.get("review_result", "")
    iteration = final_state.get("iteration", 0)

    # Определяем статус
    approved = "APPROVED" in review.upper() if review else False
    status = "success" if approved else "needs_review"

    return json.dumps({
        "status": status,
        "summary": f"Задача выполнена за {iteration} итераций. {'Ревью пройдено.' if approved else 'Требуется доработка.'}",
        "plan": plan,
        "code": code,
        "review": review,
        "iterations": iteration,
        "files": _parse_code_files(code),
    }, ensure_ascii=False, default=str)


async def _run_with_worker(
    cfg: MCPConfig,
    task_text: str,
    complexity: str = "auto",
    project_files: int = 0,
) -> str:
    """Запускает рой через SwarmWorker (с кэшем и rate limiter).

    Args:
        cfg: конфигурация MCP-сервера
        task_text: текст задачи
        complexity: подсказка сложности
        project_files: количество файлов в проекте

    Returns:
        str: JSON с результатами
    """
    import uuid

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
        return json.dumps({"status": "error", "error": result.error}, ensure_ascii=False)

    plan = result.plan or ""
    code = result.code or ""
    review = result.review_result or ""
    approved = "APPROVED" in review.upper() if review else False

    return json.dumps({
        "status": "success" if approved else "needs_review",
        "summary": (
            f"Задача выполнена за {result.iterations} итераций. "
            f"{'Результат из кэша. ' if result.cached else ''}"
            f"{'Ревью пройдено.' if approved else 'Требуется доработка.'}"
        ),
        "plan": plan,
        "code": code,
        "review": review,
        "iterations": result.iterations,
        "cached": result.cached,
        "tokens": {
            "total": result.total_tokens,
            "cost_usd": result.cost_usd,
        },
        "duration_sec": result.duration_sec,
        "files": _parse_code_files(code),
    }, ensure_ascii=False, default=str)


def _parse_code_files(code: str) -> list[dict]:
    """Парсит сгенерированный код для определения списка файлов.

    Анализирует блоки кода с комментариями вида:
        # file: path/to/file.py
        или
        // file: path/to/file.js

    Args:
        code: сгенерированный код

    Returns:
        list[dict]: список файлов с путями
    """
    files = []
    if not code:
        return files

    import re
    # Ищем паттерны: # file: path, // file: path, <!-- file: path -->
    pattern = r'(?:#|//|<!--)\s*file:\s*(\S+)'
    matches = re.findall(pattern, code, re.IGNORECASE)
    for m in matches:
        files.append({"path": m, "action": "created"})

    # Если не нашли пометок, возвращаем весь код как один "файл"
    if not files:
        files.append({"path": "generated_code", "action": "generated"})

    return files


# --------------------------------------------------------------------------- #
# Точка входа
# --------------------------------------------------------------------------- #

async def main() -> None:
    """Точка входа. Запускает MCP-сервер через stdio."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    logger.info("Starting Swarm MCP server...")
    logger.info("Available tools: run_swarm, swarm_status, swarm_ask, swarm_execute, swarm_files")

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
