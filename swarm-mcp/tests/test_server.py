"""Mock-тесты MCP-сервера swarm-mcp (v2.0.0 — продуктовые инструменты)."""

from __future__ import annotations

import json
import os
import sys
from typing import Any, AsyncGenerator
from unittest.mock import MagicMock, patch

import pytest

# Добавляем путь к src для импорта пакета
_SRC_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

# Добавляем путь к корню проекта для импорта swarm
_PROJECT_ROOT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..")
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from mcp.types import (
    ListToolsRequest,
    CallToolRequest,
    CallToolRequestParams,
    ServerResult,
    ListToolsResult,
    CallToolResult,
)

from swarm_mcp.server import create_server
from swarm_mcp.config import MCPConfig


# --------------------------------------------------------------------------- #
# Helper: создаёт сервер с заданным ключом API
# --------------------------------------------------------------------------- #

def _make_server(api_key: str = "test-key-12345"):
    """Создаёт экземпляр MCP-сервера с mock-конфигом."""
    from swarm.config import SwarmConfig
    swarm_cfg = SwarmConfig(deepseek_api_key=api_key)
    mcp_cfg = MCPConfig(swarm_config=swarm_cfg)
    return create_server(mcp_cfg)


def _make_list_tools_req():
    """Создаёт ListToolsRequest."""
    return ListToolsRequest(method="tools/list", params=None)


def _make_call_tool_req(name: str = "run_swarm", arguments: dict | None = None):
    """Создаёт CallToolRequest."""
    return CallToolRequest(
        method="tools/call",
        params=CallToolRequestParams(
            name=name,
            arguments=arguments or {},
        ),
    )


# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #

@pytest.fixture
def mock_swarm_runner():
    """Создаёт mock для SwarmRunner с async stream."""
    with patch("swarm_mcp.server.SwarmRunner") as mock:
        instance = mock.return_value

        async def stream_side_effect(
            task: str, thread_id: str = "default"
        ) -> AsyncGenerator[dict[str, Any], dict[str, Any]]:
            yield {"node": "architect", "label": "Архитектор", "emoji": "ARCH",
                   "output": {"plan": "Test plan"}}
            yield {"node": "coder", "label": "Кодер", "emoji": "CODE",
                   "output": {"code": "print('hello')"}}
            yield {"node": "reviewer", "label": "Ревьюер", "emoji": "REVW",
                   "output": {"review_result": "APPROVED"}}

        instance.stream = stream_side_effect
        instance._last_result = {
            "plan": "Test plan",
            "code": "print('hello')",
            "review_result": "APPROVED",
            "iteration": 1,
        }
        yield instance


# --------------------------------------------------------------------------- #
# Tests: Create Server
# --------------------------------------------------------------------------- #

class TestCreateServer:
    """Тесты создания сервера."""

    def test_server_created(self):
        """Сервер должен создаваться и иметь имя 'swarm'."""
        from mcp.server import Server
        server = _make_server()
        assert isinstance(server, Server)
        assert server.name == "swarm"

    @pytest.mark.asyncio
    async def test_list_tools_registers_all_tools(self):
        """Должны быть зарегистрированы все 5 инструментов."""
        server = _make_server()
        handler = server.request_handlers[ListToolsRequest]
        result: ServerResult = await handler(_make_list_tools_req())

        assert isinstance(result, ServerResult)
        assert isinstance(result.root, ListToolsResult)
        tools = result.root.tools
        assert len(tools) == 5

        tool_names = [t.name for t in tools]
        assert "run_swarm" in tool_names
        assert "swarm_status" in tool_names
        assert "swarm_ask" in tool_names
        assert "swarm_execute" in tool_names
        assert "swarm_files" in tool_names

    @pytest.mark.asyncio
    async def test_run_swarm_schema(self):
        """run_swarm должен иметь правильную схему."""
        server = _make_server()
        handler = server.request_handlers[ListToolsRequest]
        result: ServerResult = await handler(_make_list_tools_req())

        run_swarm = [t for t in result.root.tools if t.name == "run_swarm"][0]
        assert run_swarm.inputSchema is not None
        assert run_swarm.inputSchema["type"] == "object"
        assert "task" in run_swarm.inputSchema["properties"]
        assert "task" in run_swarm.inputSchema["required"]
        assert "context" in run_swarm.inputSchema["properties"]
        assert "mode" in run_swarm.inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_swarm_status_schema(self):
        """swarm_status должен иметь правильную схему (scope опциональный)."""
        server = _make_server()
        handler = server.request_handlers[ListToolsRequest]
        result: ServerResult = await handler(_make_list_tools_req())

        status_tool = [t for t in result.root.tools if t.name == "swarm_status"][0]
        assert "scope" in status_tool.inputSchema["properties"]

    @pytest.mark.asyncio
    async def test_swarm_ask_schema(self):
        """swarm_ask должен иметь question как required."""
        server = _make_server()
        handler = server.request_handlers[ListToolsRequest]
        result: ServerResult = await handler(_make_list_tools_req())

        ask_tool = [t for t in result.root.tools if t.name == "swarm_ask"][0]
        assert "question" in ask_tool.inputSchema["properties"]
        assert "question" in ask_tool.inputSchema["required"]

    @pytest.mark.asyncio
    async def test_swarm_execute_schema(self):
        """swarm_execute должен иметь command как required."""
        server = _make_server()
        handler = server.request_handlers[ListToolsRequest]
        result: ServerResult = await handler(_make_list_tools_req())

        exec_tool = [t for t in result.root.tools if t.name == "swarm_execute"][0]
        assert "command" in exec_tool.inputSchema["properties"]
        assert "command" in exec_tool.inputSchema["required"]

    @pytest.mark.asyncio
    async def test_swarm_files_schema(self):
        """swarm_files должен иметь pattern как required."""
        server = _make_server()
        handler = server.request_handlers[ListToolsRequest]
        result: ServerResult = await handler(_make_list_tools_req())

        files_tool = [t for t in result.root.tools if t.name == "swarm_files"][0]
        assert "pattern" in files_tool.inputSchema["properties"]
        assert "pattern" in files_tool.inputSchema["required"]


# --------------------------------------------------------------------------- #
# Tests: Call Tool — run_swarm
# --------------------------------------------------------------------------- #

class TestCallRunSwarm:
    """Тесты вызова run_swarm."""

    @pytest.mark.asyncio
    async def test_empty_task_returns_error(self):
        """Пустая задача должна возвращать ошибку."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(arguments={"task": ""})
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_error(self):
        """При отсутствии API-ключа должна возвращаться ошибка."""
        server = _make_server(api_key="")
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(arguments={"task": "test task"})
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        assert "error" in data
        assert "API_KEY" in data["error"]

    @pytest.mark.asyncio
    async def test_successful_run_returns_json(self, mock_swarm_runner):
        """Успешный запуск роя должен возвращать JSON."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(arguments={"task": "Write a function"})
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)

        # Должен содержать ключи результата
        assert "status" in data
        assert "plan" in data
        assert "code" in data
        assert "review" in data
        assert "iterations" in data
        assert "files" in data

    @pytest.mark.asyncio
    async def test_plan_mode_returns_plan(self, mock_swarm_runner):
        """Режим 'plan' должен возвращать план без кода."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(arguments={"task": "test", "mode": "plan"})
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        assert data.get("mode") == "plan"

    @pytest.mark.asyncio
    async def test_exception_during_run_returns_error(self):
        """Исключение при выполнении должно возвращать ошибку."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]

        with patch("swarm_mcp.server.SwarmRunner") as mock_runner:
            instance = mock_runner.return_value

            async def failing_stream(task, thread_id="default"):
                raise Exception("Test API error")
                yield  # pragma: no cover

            instance.stream = failing_stream

            result: ServerResult = await handler(
                _make_call_tool_req(arguments={"task": "test"})
            )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        assert "Test API error" in data.get("error", "")

    @pytest.mark.asyncio
    async def test_run_with_context(self, mock_swarm_runner):
        """Задача с дополнительным контекстом."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(arguments={
                "task": "Write a function",
                "context": "Use FastAPI",
            })
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        assert data.get("status") in ("success", "needs_review")


# --------------------------------------------------------------------------- #
# Tests: Call Tool — swarm_status
# --------------------------------------------------------------------------- #

class TestCallSwarmStatus:
    """Тесты вызова swarm_status."""

    @pytest.mark.asyncio
    async def test_summary_status(self):
        """swarm_status с scope='summary' должен возвращать краткую сводку."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(name="swarm_status", arguments={})
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        # Должен содержать базовые ключи
        assert "project" in data or "files_total" in data
        assert "tests" in data or "git_branch" in data

    @pytest.mark.asyncio
    async def test_full_status(self):
        """swarm_status с scope='full' должен возвращать детальный анализ."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(name="swarm_status", arguments={"scope": "full"})
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        assert "files" in data
        assert "structure" in data
        assert "git" in data


# --------------------------------------------------------------------------- #
# Tests: Call Tool — swarm_ask
# --------------------------------------------------------------------------- #

class TestCallSwarmAsk:
    """Тесты вызова swarm_ask."""

    @pytest.mark.asyncio
    async def test_empty_question_returns_error(self):
        """Пустой вопрос должен возвращать ошибку."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(name="swarm_ask", arguments={"question": ""})
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_ask_about_architecture(self):
        """Вопрос об архитектуре должен возвращать ответ."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(name="swarm_ask", arguments={"question": "Какая архитектура проекта?"})
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        assert "answer" in data
        assert data["category"] == "architecture"

    @pytest.mark.asyncio
    async def test_ask_about_security(self):
        """Вопрос о безопасности должен возвращать ответ."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(name="swarm_ask", arguments={"question": "Есть ли уязвимости?"})
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        assert "answer" in data


# --------------------------------------------------------------------------- #
# Tests: Call Tool — swarm_execute
# --------------------------------------------------------------------------- #

class TestCallSwarmExecute:
    """Тесты вызова swarm_execute."""

    @pytest.mark.asyncio
    async def test_empty_command_returns_error(self):
        """Пустая команда должна возвращать ошибку."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(name="swarm_execute", arguments={"command": ""})
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_safe_command_executes(self):
        """Команда из auto_allow должна выполняться."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(name="swarm_execute", arguments={"command": "python --version", "approved": True})
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        assert "return_code" in data

    @pytest.mark.asyncio
    async def test_blocked_command_returns_error(self):
        """Команда из deny-списка должна блокироваться."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(name="swarm_execute", arguments={"command": "rm -rf /"})
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        assert "denied" in data.get("error", "").lower() or "denied" in str(data)


# --------------------------------------------------------------------------- #
# Tests: Call Tool — swarm_files
# --------------------------------------------------------------------------- #

class TestCallSwarmFiles:
    """Тесты вызова swarm_files."""

    @pytest.mark.asyncio
    async def test_empty_pattern_returns_error(self):
        """Пустой pattern должен возвращать ошибку."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(name="swarm_files", arguments={"pattern": ""})
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        assert "error" in data

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        """Неизвестный инструмент должен возвращать ошибку."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(name="unknown_tool")
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text
        data = json.loads(text)
        assert "error" in data
        assert "Unknown tool" in data["error"]
        # Ошибка передаётся через TextContent(isError=True), а не через CallToolResult.isError
        assert result.root.content[0].isError is True


# --------------------------------------------------------------------------- #
# Tests: MCPConfig
# --------------------------------------------------------------------------- #

class TestMCPConfig:
    """Тесты конфигурации MCP."""

    def test_default_config(self):
        """MCPConfig должен иметь разумные значения по умолчанию."""
        config = MCPConfig()
        assert config.server_name == "swarm"
        assert config.server_version == "2.0.0"
        assert config.swarm is not None
        assert config.orchestration_enabled is True

    def test_config_with_custom_swarm(self):
        """MCPConfig должен принимать кастомный SwarmConfig."""
        from swarm.config import SwarmConfig

        swarm_cfg = SwarmConfig(
            deepseek_api_key="custom-key",
            max_iterations=5,
        )
        config = MCPConfig(swarm_config=swarm_cfg)
        assert config.swarm.deepseek_api_key == "custom-key"
        assert config.swarm.max_iterations == 5

    def test_from_env_creates_config(self, monkeypatch):
        """MCPConfig.from_env() должен загружать конфигурацию."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "env-key")
        config = MCPConfig.from_env()
        assert config.swarm.deepseek_api_key == "env-key"

    def test_orchestration_env(self, monkeypatch):
        """MCP_ORCHESTRATION=false должен отключать инструменты."""
        monkeypatch.setenv("MCP_ORCHESTRATION", "false")
        config = MCPConfig()
        assert config.orchestration_enabled is False


# --------------------------------------------------------------------------- #
# Tests: Package
# --------------------------------------------------------------------------- #

class TestPackage:
    """Тесты пакета swarm_mcp."""

    def test_version(self):
        """Пакет должен экспортировать версию 2.0.0."""
        import swarm_mcp
        assert swarm_mcp.__version__ == "2.0.0"

    def test_public_api(self):
        """Пакет должен экспортировать все публичные символы."""
        import swarm_mcp
        assert hasattr(swarm_mcp, "create_server")
        assert hasattr(swarm_mcp, "main")
        assert hasattr(swarm_mcp, "MCPConfig")
        assert swarm_mcp.__all__ == ["create_server", "main", "MCPConfig"]


def test_run_with_worker_config():
    """Проверяет, что MCPConfig с use_worker=True создаётся корректно."""
    os.environ["MCP_USE_WORKER"] = "true"

    config = MCPConfig()
    assert config.use_worker == True, "use_worker should be True"

    server = create_server(config)
    assert server is not None, "Server should be created"
