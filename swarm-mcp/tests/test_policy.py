"""Тесты для модуля policy.py — политики безопасности."""

from __future__ import annotations

import os
import sys
import tempfile

import pytest

_SRC_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

from swarm_mcp.policy import (
    SafetyPolicy,
    load_policy,
    classify_command,
    _DEFAULT_AUTO_ALLOW,
    _DEFAULT_REQUIRE_APPROVAL,
    _DEFAULT_DENY,
)


class TestSafetyPolicy:
    """Тесты SafetyPolicy."""

    def test_default_policy(self):
        """Политика по умолчанию должна иметь все категории."""
        policy = SafetyPolicy()
        assert len(policy.auto_allow_commands) > 0
        assert len(policy.require_approval) > 0
        assert len(policy.deny_commands) > 0
        assert policy.max_execution_time == 120
        assert policy.max_concurrent == 2

    def test_default_contains_expected(self):
        """Политика по умолчанию должна содержать ожидаемые команды."""
        policy = SafetyPolicy()
        assert "pip install" in policy.auto_allow_commands
        assert "pytest" in policy.auto_allow_commands
        assert "git push" in policy.require_approval
        assert "rm -rf /" in policy.deny_commands


class TestClassifyCommand:
    """Тесты classify_command."""

    def test_auto_allow_pip_install(self):
        """pip install должен быть auto_allow."""
        policy = SafetyPolicy()
        assert classify_command("pip install requests", policy) == "auto_allow"

    def test_auto_allow_pytest(self):
        """pytest должен быть auto_allow."""
        policy = SafetyPolicy()
        assert classify_command("pytest tests/ -v", policy) == "auto_allow"

    def test_require_approval_git_push(self):
        """git push должен требовать approval."""
        policy = SafetyPolicy()
        assert classify_command("git push origin main", policy) == "require_approval"

    def test_deny_rm_rf_root(self):
        """rm -rf / должен быть заблокирован."""
        policy = SafetyPolicy()
        assert classify_command("rm -rf /", policy) == "deny"

    def test_deny_chmod_777(self):
        """chmod 777 должен быть заблокирован."""
        policy = SafetyPolicy()
        assert classify_command("chmod -R 777 /etc", policy) == "deny"

    def test_unknown_command_requires_approval(self):
        """Неизвестная команда должна требовать approval."""
        policy = SafetyPolicy()
        assert classify_command("some_obscure_tool --danger", policy) == "require_approval"

    def test_case_insensitive(self):
        """Классификация должна быть case-insensitive."""
        policy = SafetyPolicy()
        assert classify_command("PIP INSTALL flask", policy) == "auto_allow"
        assert classify_command("GIT PUSH", policy) == "require_approval"
        assert classify_command("RM -RF /", policy) == "deny"

    def test_partial_match_deny(self):
        """Частичное совпадение с deny должно блокировать."""
        policy = SafetyPolicy()
        assert classify_command("sudo rm -rf /some/dir", policy) == "deny"


class TestLoadPolicy:
    """Тесты load_policy."""

    def test_load_default_when_no_file(self, tmp_path):
        """Если .swarm-policy.toml не существует, должны быть политики по умолчанию."""
        policy = load_policy(str(tmp_path))
        assert isinstance(policy, SafetyPolicy)
        assert "pytest" in policy.auto_allow_commands

    def test_load_from_toml_file(self, tmp_path):
        """Загрузка политик из .swarm-policy.toml."""
        policy_path = os.path.join(tmp_path, ".swarm-policy.toml")
        with open(policy_path, "w", encoding="utf-8") as f:
            f.write("""
[safety]
auto_allow_commands = ["echo", "ls"]
require_approval = ["deploy"]
deny_commands = ["danger"]
max_execution_time = 60
max_concurrent = 1
""")

        policy = load_policy(str(tmp_path))
        assert "echo" in policy.auto_allow_commands
        assert "deploy" in policy.require_approval
        assert "danger" in policy.deny_commands
        assert policy.max_execution_time == 60
        assert policy.max_concurrent == 1

    def test_custom_policy_classification(self, tmp_path):
        """Проверка классификации с кастомными политиками."""
        policy_path = os.path.join(tmp_path, ".swarm-policy.toml")
        with open(policy_path, "w", encoding="utf-8") as f:
            f.write("""
[safety]
auto_allow_commands = ["safe_cmd"]
deny_commands = ["bad_cmd"]
""")

        policy = load_policy(str(tmp_path))
        assert classify_command("safe_cmd --help", policy) == "auto_allow"
        assert classify_command("bad_cmd --all", policy) == "deny"
        assert classify_command("unknown_cmd", policy) == "require_approval"
