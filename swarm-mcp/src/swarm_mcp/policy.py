"""Политики безопасности для Swarm MCP.

Загружает .swarm-policy.toml из корня проекта и определяет,
какие команды можно запускать без подтверждения, какие требуют
одобрения пользователя, а какие запрещены.
"""

from __future__ import annotations

import logging
import os
import shlex
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("swarm-mcp.policy")


# --------------------------------------------------------------------------- #
# Политики по умолчанию
# --------------------------------------------------------------------------- #

_DEFAULT_AUTO_ALLOW = [
    "pip install",
    "npm install",
    "git status",
    "git diff",
    "git log",
    "python -m pytest",
    "python -m unittest",
    "pytest",
    "node --version",
    "python --version",
    "python --help",
    "which",
    "where",
    "ls",
    "dir",
    "type",
    "cat",
    "findstr",
    "find",
]

_DEFAULT_REQUIRE_APPROVAL = [
    "git push",
    "git commit",
    "git merge",
    "git rebase",
    "rm -rf",
    "rmdir",
    "del /s",
    "sudo",
    "docker",
    "kubectl",
    "terraform",
    "helm install",
    "helm upgrade",
    "pip uninstall",
    "npm uninstall",
    "npm publish",
]

_DEFAULT_DENY = [
    "rm -rf /",
    "rm -rf ~",
    "rmdir /s /q",
    "chmod -R 777",
    "chmod 777",
    "> /dev/sda",
    "dd if=",
    "mkfs",
    "fdisk",
    "format",
    ":(){ :|:& };:",
    "fork bomb",
    # Shell injection / pipe vectors
    "curl |",
    "curl|",
    "wget |",
    "wget|",
    "| bash",
    "| sh",
    "| powershell",
    "| cmd",
    "`",
    "$(eval",
    "eval ",
]


@dataclass
class SafetyPolicy:
    """Политика безопасности для выполнения команд.

    Attributes:
        auto_allow_commands: команды, выполняемые без подтверждения.
        require_approval: команды, требующие одобрения пользователя.
        deny_commands: команды, которые заблокированы полностью.
        max_execution_time: максимальное время выполнения (сек).
        max_concurrent: максимум одновременных команд.
    """

    auto_allow_commands: list[str] = field(default_factory=lambda: _DEFAULT_AUTO_ALLOW.copy())
    require_approval: list[str] = field(default_factory=lambda: _DEFAULT_REQUIRE_APPROVAL.copy())
    deny_commands: list[str] = field(default_factory=lambda: _DEFAULT_DENY.copy())
    max_execution_time: int = 120
    max_concurrent: int = 2


def _try_load_toml(path: str) -> Optional[dict]:
    """Пытается загрузить TOML-файл стандартной библиотекой или tomli.

    Args:
        path: путь к .toml файлу.

    Returns:
        dict | None: содержимое файла или None при ошибке.
    """
    try:
        import tomllib  # Python 3.11+
        with open(path, "rb") as f:
            return tomllib.load(f)
    except ImportError:
        pass
    except Exception as e:
        logger.debug("tomllib failed: %s", e)

    try:
        import tomli
        with open(path, "rb") as f:
            return tomli.load(f)
    except ImportError:
        logger.warning("tomli not installed — using default policies")
    except Exception as e:
        logger.debug("tomli failed: %s", e)

    return None


def load_policy(project_root: str | None = None) -> SafetyPolicy:
    """Загружает политики из .swarm-policy.toml (или возвращает default).

    Args:
        project_root: корень проекта. Если None, определяется
                     как текущая рабочая директория.

    Returns:
        SafetyPolicy: загруженная политика.
    """
    root = project_root or os.getcwd()
    policy_path = os.path.join(root, ".swarm-policy.toml")

    if not os.path.exists(policy_path):
        logger.info("No .swarm-policy.toml found, using defaults")
        return SafetyPolicy()

    data = _try_load_toml(policy_path)
    if data is None:
        logger.warning("Failed to parse %s, using defaults", policy_path)
        return SafetyPolicy()

    safety = data.get("safety", {})
    return SafetyPolicy(
        auto_allow_commands=safety.get("auto_allow_commands", _DEFAULT_AUTO_ALLOW.copy()),
        require_approval=safety.get("require_approval", _DEFAULT_REQUIRE_APPROVAL.copy()),
        deny_commands=safety.get("deny_commands", _DEFAULT_DENY.copy()),
        max_execution_time=safety.get("max_execution_time", 120),
        max_concurrent=safety.get("max_concurrent", 2),
    )


def classify_command(command: str, policy: SafetyPolicy) -> str:
    """Классифицирует команду по уровню безопасности (token-based).

    Использует shlex.split для разбиения команды на токены,
    что предотвращает shell-инъекции через substring match.

    Args:
        command: команда для классификации.
        policy: политика безопасности.

    Returns:
        str: "auto_allow" | "require_approval" | "deny"
    """
    try:
        tokens = shlex.split(command.strip().lower())
    except ValueError:
        # Если shlex.split упал (незакрытые кавычки) — require_approval
        return "require_approval"

    if not tokens:
        return "require_approval"

    # ---- Проверка deny (token-based последовательность) ----
    for deny_pattern in policy.deny_commands:
        try:
            deny_tokens = shlex.split(deny_pattern.lower())
        except ValueError:
            continue
        if len(deny_tokens) > len(tokens):
            continue
        for i in range(len(tokens) - len(deny_tokens) + 1):
            match = True
            for j in range(len(deny_tokens)):
                if deny_tokens[j] not in tokens[i + j]:
                    match = False
                    break
            if match:
                return "deny"

    # ---- Проверка auto_allow (prefix match по токенам) ----
    for allow_pattern in policy.auto_allow_commands:
        try:
            allow_tokens = shlex.split(allow_pattern.lower())
        except ValueError:
            continue
        if len(allow_tokens) <= len(tokens):
            if tokens[: len(allow_tokens)] == allow_tokens:
                # Подозрительные операторы в команде — require_approval
                suspicious = ["&&", "||", "|", ";", "`", "$("]
                if any(s in command for s in suspicious):
                    return "require_approval"
                return "auto_allow"

    # ---- Проверка require_approval (prefix match по токенам) ----
    for approve_pattern in policy.require_approval:
        try:
            approve_tokens = shlex.split(approve_pattern.lower())
        except ValueError:
            continue
        if len(approve_tokens) <= len(tokens):
            if tokens[: len(approve_tokens)] == approve_tokens:
                return "require_approval"

    # Неизвестная команда — требуется подтверждение
    return "require_approval"
