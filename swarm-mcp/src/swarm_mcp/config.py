"""Конфигурация MCP-сервера."""

import os
from typing import Optional

from swarm.config import SwarmConfig


class MCPConfig:
    """Конфигурация с общими настройками для MCP.

    Оборачивает SwarmConfig и добавляет параметры,
    специфичные для MCP-сервера (имя, версия, orchestration).

    Поддерживает опциональное использование SwarmWorker
    с кэшем и rate limiter вместо прямого SwarmRunner.
    """

    def __init__(self, swarm_config: Optional[SwarmConfig] = None) -> None:
        """Инициализирует MCPConfig.

        Args:
            swarm_config: готовая конфигурация роя.
                         Если None, загружается из .env автоматически.
        """
        self.swarm = swarm_config or SwarmConfig.from_env()
        self.server_name: str = "swarm"
        self.server_version: str = "2.0.0"

        # Опциональное использование SwarmWorker (с кэшем и rate limiter)
        self.use_worker: bool = (
            os.getenv("MCP_USE_WORKER", "false").lower() == "true"
        )

        # Продуктовые инструменты
        self.orchestration_enabled: bool = (
            os.getenv("MCP_ORCHESTRATION", "true").lower() == "true"
        )

        # Безопасность
        self.enable_executor: bool = (
            os.getenv("MCP_ENABLE_EXECUTOR", "true").lower() == "true"
        )

    @classmethod
    def from_env(cls, env_path: Optional[str] = None) -> "MCPConfig":
        """Загружает конфигурацию из .env файла.

        Args:
            env_path: путь к .env файлу.

        Returns:
            MCPConfig: загруженная конфигурация.
        """
        swarm_config = SwarmConfig.from_env(env_path)
        return cls(swarm_config=swarm_config)
