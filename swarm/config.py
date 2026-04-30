"""Конфигурация для Swarm AI-агентов."""

import os
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

from swarm.llm import BaseLLMProvider, LiteLLMConfig, LiteLLMProvider


@dataclass
class SwarmConfig:
    """Конфигурация роя AI-агентов.

    Поля:
        deepseek_api_key: API-ключ DeepSeek (для обратной совместимости)
        architect_model_name: модель для архитектора
        coder_model_name: модель для кодера
        reviewer_model_name: модель для ревьюера
        base_url: базовый URL API DeepSeek
        temperature: температура модели (низкая для предсказуемости)
        max_iterations: максимальное количество циклов кодер→ревьюер
        llm_provider: экземпляр провайдера LLM (LiteLLM)
    """

    deepseek_api_key: str = ""
    architect_model_name: str = "deepseek-chat"
    coder_model_name: str = "deepseek-chat"
    reviewer_model_name: str = "deepseek-chat"
    base_url: str = "https://api.deepseek.com/v1"
    temperature: float = 0.1
    max_iterations: int = 3
    llm_provider: Optional[BaseLLMProvider] = None  # инициализируется в from_env()

    @classmethod
    def from_env(cls, env_path: Optional[str] = None) -> "SwarmConfig":
        """Загружает конфигурацию из .env файла.

        Args:
            env_path: путь к .env файлу (по умолчанию ищет в текущей директории)

        Returns:
            SwarmConfig: загруженная конфигурация
        """
        load_dotenv(dotenv_path=env_path)

        config = cls(
            deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            architect_model_name=os.getenv("ARCHITECT_MODEL", "deepseek-chat"),
            coder_model_name=os.getenv("CODER_MODEL", "deepseek-chat"),
            reviewer_model_name=os.getenv("REVIEWER_MODEL", "deepseek-chat"),
            base_url=os.getenv("BASE_URL", "https://api.deepseek.com/v1"),
            temperature=float(os.getenv("TEMPERATURE", "0.1")),
            max_iterations=int(os.getenv("MAX_ITERATIONS", "3")),
        )

        # Создаём провайдер LiteLLM
        llm_config = LiteLLMConfig.from_env()
        config.llm_provider = LiteLLMProvider.from_config(llm_config)

        return config

    def get_architect_llm(self) -> BaseLLMProvider:
        """Возвращает LLM провайдер для архитектора.

        Returns:
            BaseLLMProvider: провайдер LLM
        """
        if self.llm_provider is None:
            self.llm_provider = LiteLLMProvider()
        return self.llm_provider

    def get_coder_llm(self) -> BaseLLMProvider:
        """Возвращает LLM провайдер для кодера.

        Returns:
            BaseLLMProvider: провайдер LLM
        """
        if self.llm_provider is None:
            self.llm_provider = LiteLLMProvider()
        return self.llm_provider

    def get_reviewer_llm(self) -> BaseLLMProvider:
        """Возвращает LLM провайдер для ревьюера.

        Returns:
            BaseLLMProvider: провайдер LLM
        """
        if self.llm_provider is None:
            self.llm_provider = LiteLLMProvider()
        return self.llm_provider
