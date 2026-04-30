"""LLM Provider Abstraction — абстракция провайдера LLM.

Позволяет переключаться между разными AI-провайдерами
(DeepSeek, OpenAI, Anthropic, Groq и др.) через единый интерфейс.
"""

from .base import BaseLLMProvider, LLMResponse
from .litellm_provider import LiteLLMProvider
from .config import LiteLLMConfig

__all__ = ["BaseLLMProvider", "LLMResponse", "LiteLLMProvider", "LiteLLMConfig"]
