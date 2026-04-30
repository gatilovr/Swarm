"""Mock-тесты MCP-сервера swarm-mcp."""

from __future__ import annotations

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
        }
        yield instance


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

class TestCreateServer:
    """Тесты создания сервера."""

    def test_server_created(self):
        """Сервер должен создаваться и иметь имя 'code-swarm'."""
        from mcp.server import Server
        server = _make_server()
        assert isinstance(server, Server)
        assert server.name == "code-swarm"

    @pytest.mark.asyncio
    async def test_list_tools_registers_run_swarm(self):
        """Должен быть зарегистрирован инструмент run_swarm с правильной схемой."""
        server = _make_server()
        handler = server.request_handlers[ListToolsRequest]
        result: ServerResult = await handler(_make_list_tools_req())

        assert isinstance(result, ServerResult)
        assert isinstance(result.root, ListToolsResult)
        tools = result.root.tools
        assert len(tools) == 1

        tool = tools[0]
        assert tool.name == "run_swarm"
        assert "Архитектор" in tool.description
        assert "Кодер" in tool.description
        assert "Ревьюер" in tool.description
        assert tool.inputSchema is not None
        assert tool.inputSchema["type"] == "object"
        assert "task" in tool.inputSchema["properties"]
        assert tool.inputSchema["properties"]["task"]["type"] == "string"
        assert "task" in tool.inputSchema["required"]


class TestCallTool:
    """Тесты вызова инструментов."""

    @pytest.mark.asyncio
    async def test_empty_task_returns_error(self):
        """Пустая задача должна возвращать сообщение об ошибке."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(arguments={"task": ""})
        )

        assert isinstance(result.root, CallToolResult)
        assert len(result.root.content) == 1
        text = result.root.content[0].text
        assert "ERROR" in text
        assert "task" in text.lower()

    @pytest.mark.asyncio
    async def test_missing_task_param_returns_error(self):
        """Отсутствующий параметр task должен возвращать ошибку."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(arguments={})
        )

        assert isinstance(result.root, CallToolResult)
        # MCP Server validates inputSchema — возвращает ошибку валидации
        assert len(result.root.content) == 1
        text = result.root.content[0].text
        assert "required property" in text or "validation error" in text.lower()

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        """Неизвестный инструмент должен возвращать ошибку."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(name="unknown_tool")
        )

        assert isinstance(result.root, CallToolResult)
        assert result.root.isError
        assert "Unknown tool" in result.root.content[0].text

    @pytest.mark.asyncio
    async def test_missing_api_key_returns_error(self):
        """При отсутствии API-ключа должна возвращаться ошибка."""
        server = _make_server(api_key="")
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(arguments={"task": "test task"})
        )

        assert isinstance(result.root, CallToolResult)
        assert len(result.root.content) == 1
        text = result.root.content[0].text
        assert "ERROR" in text
        assert "API_KEY" in text

    @pytest.mark.asyncio
    async def test_successful_run_returns_formatted_result(self, mock_swarm_runner):
        """Успешный запуск роя должен возвращать структурированный результат."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]
        result: ServerResult = await handler(
            _make_call_tool_req(arguments={"task": "Write a function"})
        )

        assert isinstance(result.root, CallToolResult)
        text = result.root.content[0].text

        # Должен содержать план
        assert "План архитектора" in text
        assert "Test plan" in text

        # Должен содержать код
        assert "Итоговый код" in text
        assert "print('hello')" in text

        # Должен содержать результат ревью
        assert "Результат ревью" in text
        assert "APPROVED" in text

    @pytest.mark.asyncio
    async def test_exception_during_run_returns_error(self):
        """Исключение при выполнении должно возвращать сообщение об ошибке."""
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
        # MCP Server оборачивает результат в CallToolResult с isError=False,
        # но текст ошибки должен присутствовать
        assert "Test API error" in result.root.content[0].text

    @pytest.mark.asyncio
    async def test_empty_result_returns_fallback_message(self, mock_swarm_runner):
        """Если рой не вернул результат, должно быть сообщение-заглушка."""
        server = _make_server()
        handler = server.request_handlers[CallToolRequest]

        mock_swarm_runner._last_result = {}

        async def empty_stream(task, thread_id="default"):
            # async generator that yields nothing
            if False:
                yield

        mock_swarm_runner.stream = empty_stream

        result: ServerResult = await handler(
            _make_call_tool_req(arguments={"task": "test"})
        )

        assert isinstance(result.root, CallToolResult)
        assert "не вернул результат" in result.root.content[0].text


class TestMCPConfig:
    """Тесты конфигурации MCP."""

    def test_default_config(self):
        """MCPConfig должен иметь разумные значения по умолчанию."""
        config = MCPConfig()
        assert config.server_name == "code-swarm"
        assert config.server_version == "1.0.0"
        assert config.swarm is not None

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


class TestPackage:
    """Тесты пакета swarm_mcp."""

    def test_version(self):
        """Пакет должен экспортировать версию."""
        import swarm_mcp
        assert swarm_mcp.__version__ == "1.0.0"

    def test_public_api(self):
        """Пакет должен экспортировать все публичные символы."""
        import swarm_mcp
        assert hasattr(swarm_mcp, "create_server")
        assert hasattr(swarm_mcp, "main")
        assert hasattr(swarm_mcp, "MCPConfig")
        assert swarm_mcp.__all__ == ["create_server", "main", "MCPConfig"]


def test_run_with_worker_config():
    """Проверяет, что MCPConfig с use_worker=True создаётся корректно."""
    # Явно задаём use_worker=True через окружение
    os.environ["MCP_USE_WORKER"] = "true"

    config = MCPConfig()
    assert config.use_worker == True, "use_worker should be True"
    print("  [PASS] MCPConfig.use_worker=True")

    # Проверяем, что сервер создаётся с этой конфигурацией
    server = create_server(config)
    assert server is not None, "Server should be created"
    print("  [PASS] Server created with worker config")
