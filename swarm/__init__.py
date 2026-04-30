"""Пакет Swarm — Рой AI-агентов.

Система из трёх агентов (Архитектор, Кодер, Ревьюер),
которые взаимодействуют через граф LangGraph,
используя абстрактный провайдер LLM (LiteLLM Gateway).
"""

from .config import SwarmConfig
from .main import SwarmRunner
from .llm import BaseLLMProvider, LLMResponse, LiteLLMProvider, LiteLLMConfig

__all__ = [
    "SwarmRunner",
    "SwarmConfig",
    "BaseLLMProvider",
    "LLMResponse",
    "LiteLLMProvider",
    "LiteLLMConfig",
]

__version__ = "0.2.0"
