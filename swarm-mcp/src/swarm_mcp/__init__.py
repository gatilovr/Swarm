"""Swarm MCP Server — готовый MCP-продукт для роя AI-агентов."""

from .server import create_server, main
from .config import MCPConfig

__version__ = "1.0.0"
__all__ = ["create_server", "main", "MCPConfig"]
