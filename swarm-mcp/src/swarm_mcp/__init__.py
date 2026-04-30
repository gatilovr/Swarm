"""Swarm MCP Server — продуктовый AI-агент для полной разработки проекта.

Предоставляет высокоуровневые MCP-инструменты:
- run_swarm:       запуск полного цикла разработки (Architect -> Coder -> Reviewer)
- swarm_status:    состояние проекта
- swarm_ask:       вопросы по проекту
- swarm_execute:   безопасное выполнение команд
- swarm_files:     чтение файлов проекта
"""

from .server import create_server, main
from .config import MCPConfig

__version__ = "2.0.0"
__all__ = ["create_server", "main", "MCPConfig"]
