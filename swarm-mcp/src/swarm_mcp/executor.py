"""Безопасное выполнение команд терминала.

Предоставляет CommandExecutor, который проверяет команды
через SafetyPolicy перед запуском, и Sanitizer для валидации.
"""

from __future__ import annotations

import asyncio
import logging
import shlex
import time
from dataclasses import dataclass, field
from typing import Optional

from .policy import SafetyPolicy, classify_command, load_policy

logger = logging.getLogger("swarm-mcp.executor")


@dataclass
class CommandResult:
    """Результат выполнения команды.

    Attributes:
        command: выполненная команда.
        return_code: код возврата (None если не запускалась).
        stdout: stdout команды.
        stderr: stderr команды.
        duration_sec: время выполнения в секундах.
        classification: классификация безопасности.
        approved: была ли команда одобрена.
        error: сообщение об ошибке (если есть).
    """

    command: str
    return_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    duration_sec: float = 0.0
    classification: str = "unknown"
    approved: bool = False
    error: str = ""


class CommandSanitizer:
    """Проверяет команды на безопасность перед выполнением.

    Анализирует команду по политикам безопасности и возвращает
    классификацию, позволяя или запрещая выполнение.
    """

    def __init__(self, policy: Optional[SafetyPolicy] = None) -> None:
        """Инициализирует Sanitizer.

        Args:
            policy: политика безопасности. Если None, загружается по умолчанию.
        """
        self.policy = policy or load_policy()

    def check(self, command: str) -> str:
        """Проверяет команду и возвращает её классификацию.

        Args:
            command: команда для проверки.

        Returns:
            str: "auto_allow" | "require_approval" | "deny"
        """
        return classify_command(command, self.policy)

    def is_safe(self, command: str) -> bool:
        """Проверяет, можно ли выполнить команду без подтверждения.

        Args:
            command: команда для проверки.

        Returns:
            bool: True если команда в auto_allow.
        """
        return self.check(command) == "auto_allow"

    def is_blocked(self, command: str) -> bool:
        """Проверяет, заблокирована ли команда.

        Args:
            command: команда для проверки.

        Returns:
            bool: True если команда в deny-списке.
        """
        return self.check(command) == "deny"


class CommandExecutor:
    """Выполняет команды с проверкой безопасности.

    Поддерживает:
    - Классификацию команд по политикам безопасности.
    - Таймаут выполнения.
    - Отслеживание одновременных команд.
    - Форматирование результата.
    """

    def __init__(
        self,
        policy: Optional[SafetyPolicy] = None,
        sanitizer: Optional[CommandSanitizer] = None,
    ) -> None:
        """Инициализирует Executor.

        Args:
            policy: политика безопасности.
            sanitizer: санитайзер команд (если None, создаётся из policy).
        """
        self.policy = policy or load_policy()
        self.sanitizer = sanitizer or CommandSanitizer(self.policy)
        self._active_commands: set[str] = set()
        self._lock = asyncio.Lock()
        self._history: list[CommandResult] = []

    async def execute(
        self,
        command: str,
        timeout: Optional[int] = None,
        approved: bool = False,
    ) -> CommandResult:
        """Выполняет команду с проверкой безопасности.

        Args:
            command: команда для выполнения.
            timeout: таймаут в секундах (по умолч. из политики).
            approved: если True, команда считается предварительно одобренной.

        Returns:
            CommandResult: результат выполнения.
        """
        # Классификация
        classification = self.sanitizer.check(command)

        # Проверка deny
        if classification == "deny":
            result = CommandResult(
                command=command,
                classification="deny",
                approved=False,
                error=f"Command denied by policy: '{command}' is blocked",
            )
            self._history.append(result)
            return result

        # Проверка approval
        if classification == "require_approval" and not approved:
            result = CommandResult(
                command=command,
                classification="require_approval",
                approved=False,
                error="Command requires user approval",
            )
            self._history.append(result)
            return result

        # Проверка лимита одновременных команд
        async with self._lock:
            if len(self._active_commands) >= self.policy.max_concurrent:
                result = CommandResult(
                    command=command,
                    classification=classification,
                    approved=approved,
                    error=f"Too many concurrent commands (max {self.policy.max_concurrent})",
                )
                self._history.append(result)
                return result
            self._active_commands.add(command)

        try:
            # Выполнение
            max_time = timeout or self.policy.max_execution_time
            start = time.time()

            proc = await asyncio.create_subprocess_exec(
                *shlex.split(command),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=max_time,
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()
                result = CommandResult(
                    command=command,
                    classification=classification,
                    approved=approved,
                    return_code=-1,
                    stdout="",
                    stderr="",
                    duration_sec=time.time() - start,
                    error=f"Command timed out after {max_time}s",
                )
                self._history.append(result)
                return result

            duration = time.time() - start
            result = CommandResult(
                command=command,
                classification=classification,
                approved=approved,
                return_code=proc.returncode,
                stdout=stdout.decode("utf-8", errors="replace") if stdout else "",
                stderr=stderr.decode("utf-8", errors="replace") if stderr else "",
                duration_sec=duration,
            )

        except Exception as e:
            result = CommandResult(
                command=command,
                classification=classification,
                approved=approved,
                error=str(e),
            )

        finally:
            async with self._lock:
                self._active_commands.discard(command)

        self._history.append(result)
        return result

    @property
    def history(self) -> list[CommandResult]:
        """История выполненных команд."""
        return list(self._history)

    @property
    def stats(self) -> dict:
        """Статистика выполненных команд."""
        total = len(self._history)
        approved_count = sum(1 for r in self._history if r.approved)
        denied_count = sum(1 for r in self._history if r.error and "denied" in r.error)
        failed_count = sum(1 for r in self._history if r.return_code and r.return_code != 0)
        return {
            "total": total,
            "approved": approved_count,
            "denied": denied_count,
            "failed": failed_count,
            "active": len(self._active_commands),
        }
