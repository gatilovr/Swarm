"""Адаптивный выбор модели на основе сложности задачи.

Модели теперь используют provider-aware имена:
    - deepseek-chat — логическое имя для LiteLLM (DeepSeek V3, fallback на Groq)
    - deepseek-reasoner — логическое имя для LiteLLM (DeepSeek R1)
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ModelConfig:
    """Конфигурация моделей для задачи.

    Поля:
        architect: модель для агента-архитектора (логическое имя LiteLLM)
        coder: модель для агента-кодера (логическое имя LiteLLM)
        reviewer: модель для агента-ревьюера (None = без ревью)
        skip_review: флаг пропуска ревью
        temperature: температура модели
        provider: имя провайдера (всегда "litellm" для LiteLLM Gateway)
        display_name: отображаемое имя модели (опционально)
    """
    architect: str = "deepseek-chat"
    coder: str = "deepseek-chat"
    reviewer: Optional[str] = "deepseek-chat"
    skip_review: bool = False
    temperature: float = 0.1
    provider: str = "litellm"
    display_name: str = ""

    def __post_init__(self):
        if not self.display_name:
            self.display_name = self.architect


COMPLEXITY_KEYWORDS = {
    "critical": [
        "security", "vulnerability", "encryption", "auth",
        "critical", "mission-critical", "production",
    ],
    "high": [
        "architecture", "refactoring", "performance",
        "concurrency", "distributed", "database", "migration",
    ],
    "medium": [
        "feature", "bugfix", "api", "endpoint",
        "validation", "error handling",
    ],
    "low": [
        "test", "unit test", "integration test",
        "docs", "documentation", "config", "configuration",
        "format", "typo", "rename", "comment",
    ],
}


class ModelSelector:
    """Выбирает оптимальные модели для задачи.

    Принцип:
    - Простые задачи (тесты, доки): только deepseek-chat, без ревью
    - Средние (фичи, баги): deepseek-chat для всех
    - Сложные (архитектура, security): deepseek-reasoner для architect и reviewer
    """

    def __init__(self):
        self._stats = {"critical": 0, "high": 0, "medium": 0, "low": 0}

    def select(self, task_content: str, force_complexity: Optional[str] = None) -> ModelConfig:
        """Выбирает конфигурацию моделей на основе содержания задачи.

        Args:
            task_content: текст технического задания
            force_complexity: принудительная сложность (auto/low/medium/high/critical).
                             Если None или "auto" — авто-классификация.

        Returns:
            ModelConfig: конфигурация моделей для задачи
        """
        content_lower = task_content.lower()

        # Определяем сложность: принудительно или по ключевым словам
        if force_complexity and force_complexity != "auto":
            complexity = force_complexity
        else:
            complexity = self._classify(content_lower)

        self._stats[complexity] += 1

        if complexity == "critical":
            return ModelConfig(
                architect="deepseek-reasoner",
                coder="deepseek-chat",
                reviewer="deepseek-reasoner",
                provider="litellm",
            )
        elif complexity == "high":
            return ModelConfig(
                architect="deepseek-reasoner",
                coder="deepseek-chat",
                reviewer="deepseek-chat",
                provider="litellm",
            )
        elif complexity == "medium":
            return ModelConfig(
                architect="deepseek-chat",
                coder="deepseek-chat",
                reviewer="deepseek-chat",
                provider="litellm",
            )
        else:  # low
            return ModelConfig(
                architect="deepseek-chat",
                coder="deepseek-chat",
                reviewer=None,       # без ревью — экономим 1 вызов
                skip_review=True,
                provider="litellm",
            )

    def _classify(self, content: str) -> str:
        """Классифицирует сложность задачи по ключевым словам."""
        for level, keywords in COMPLEXITY_KEYWORDS.items():
            if any(kw in content for kw in keywords):
                return level
        return "medium"

    @property
    def stats(self) -> dict:
        """Возвращает статистику распределения сложности."""
        return dict(self._stats)
