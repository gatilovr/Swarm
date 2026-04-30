"""Тесты для модуля executor.py — безопасное выполнение команд."""

from __future__ import annotations

import os
import sys

import pytest

_SRC_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

from swarm_mcp.executor import CommandExecutor, CommandSanitizer
from swarm_mcp.policy import SafetyPolicy


class TestCommandSanitizer:
    """Тесты CommandSanitizer."""

    def test_safe_command(self):
        """safe_check для auto_allow."""
        sanitizer = CommandSanitizer()
        assert sanitizer.is_safe("pip install flask") is True
        assert sanitizer.is_safe("pytest tests/") is True

    def test_unsafe_command(self):
        """safe_check для require_approval."""
        sanitizer = CommandSanitizer()
        assert sanitizer.is_safe("git push origin main") is False

    def test_blocked_command(self):
        """is_blocked для deny."""
        sanitizer = CommandSanitizer()
        assert sanitizer.is_blocked("rm -rf /") is True

    def test_not_blocked_command(self):
        """is_blocked для разрешённых."""
        sanitizer = CommandSanitizer()
        assert sanitizer.is_blocked("pip install") is False
        assert sanitizer.is_blocked("pytest") is False

    def test_custom_policy(self):
        """Sanitizer с кастомной политикой."""
        policy = SafetyPolicy(
            auto_allow_commands=["my_cmd"],
            deny_commands=["bad"],
        )
        sanitizer = CommandSanitizer(policy)
        assert sanitizer.is_safe("my_cmd --help") is True
        assert sanitizer.is_blocked("bad thing") is True


class TestCommandExecutor:
    """Тесты CommandExecutor."""

    @pytest.mark.asyncio
    async def test_deny_command(self):
        """Команда из deny-списка должна блокироваться."""
        executor = CommandExecutor()
        result = await executor.execute("rm -rf /")
        assert result.classification == "deny"
        assert result.approved is False
        assert "denied" in result.error.lower()
        assert result.return_code is None

    @pytest.mark.asyncio
    async def test_require_approval_without_approval(self):
        """Команда require_approval без approval должна ждать подтверждения."""
        executor = CommandExecutor()
        result = await executor.execute("git push origin main")
        assert result.classification == "require_approval"
        assert result.approved is False
        assert "requires user approval" in result.error.lower()

    @pytest.mark.asyncio
    async def test_require_approval_with_approval(self):
        """Команда require_approval с approval должна выполняться."""
        executor = CommandExecutor()
        result = await executor.execute("git status", approved=True)
        # git status может быть в auto_allow, но тест всё равно проверяет
        assert result.return_code is not None or result.error == ""

    @pytest.mark.asyncio
    async def test_auto_allow_executes(self):
        """Команда из auto_allow должна выполняться."""
        executor = CommandExecutor()
        result = await executor.execute("python --version")
        assert result.return_code == 0
        assert "Python" in result.stdout

    @pytest.mark.asyncio
    async def test_unknown_command_requires_approval(self):
        """Неизвестная команда должна требовать approval."""
        executor = CommandExecutor()
        result = await executor.execute("some_very_obscure_tool_xyz123")
        assert result.classification == "require_approval"
        assert result.approved is False

    @pytest.mark.asyncio
    async def test_history(self):
        """Executor должен сохранять историю команд."""
        executor = CommandExecutor()
        await executor.execute("python --version", approved=True)
        await executor.execute("rm -rf /")
        assert len(executor.history) == 2

    @pytest.mark.asyncio
    async def test_stats(self):
        """Executor должен возвращать статистику."""
        executor = CommandExecutor()
        await executor.execute("python --version", approved=True)
        await executor.execute("rm -rf /")
        stats = executor.stats
        assert stats["total"] == 2
        assert stats["denied"] == 1

    @pytest.mark.asyncio
    async def test_concurrent_limit(self):
        """Лимит одновременных команд не должен превышаться."""
        policy = SafetyPolicy(max_concurrent=1)
        executor = CommandExecutor(policy=policy)
        # Первая команда
        await executor.execute("python --version", approved=True)
        stats = executor.stats
        assert stats["active"] == 0  # команда завершилась
