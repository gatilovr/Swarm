"""Тесты для адаптивного выбора модели."""

import pytest
from swarm_scale.model_selector import ModelSelector, ModelConfig


class TestModelSelector:
    """Тесты ModelSelector."""

    def setup_method(self):
        self.selector = ModelSelector()

    def test_low_complexity(self):
        """Тесты/доки → deepseek-chat, без ревью."""
        # Тест
        config = self.selector.select("Напиши unit test для функции сортировки")
        assert config.architect == "deepseek-chat"
        assert config.coder == "deepseek-chat"
        assert config.reviewer is None
        assert config.skip_review is True

        # Документация
        config = self.selector.select("Обнови documentation для README")
        assert config.skip_review is True
        assert config.reviewer is None

        # Конфигурация
        config = self.selector.select("Измени config файл")
        assert config.skip_review is True

    def test_high_complexity(self):
        """Архитектура/security → deepseek-reasoner."""
        # Архитектура
        config = self.selector.select("Спроектируй architecture для микросервисов")
        assert config.architect == "deepseek-reasoner"
        assert config.reviewer == "deepseek-chat"
        assert config.skip_review is False

        # Security
        config = self.selector.select("Исправь vulnerability в аутентификации")
        assert config.architect == "deepseek-reasoner"

        # Performance
        config = self.selector.select("Оптимизируй performance БД")
        assert config.architect == "deepseek-reasoner"

    def test_medium_complexity(self):
        """Фичи/баги → deepseek-chat для всех."""
        # Feature
        config = self.selector.select("Реализуй новый feature для пользователей")
        assert config.architect == "deepseek-chat"
        assert config.coder == "deepseek-chat"
        assert config.reviewer == "deepseek-chat"
        assert config.skip_review is False

        # Bugfix
        config = self.selector.select("Исправь bug в обработке ошибок")
        assert config.architect == "deepseek-chat"
        assert config.reviewer == "deepseek-chat"

    def test_critical_complexity(self):
        """Critical → deepseek-reasoner для architect и reviewer."""
        config = self.selector.select("Исправь critical security vulnerability")
        assert config.architect == "deepseek-reasoner"
        assert config.reviewer == "deepseek-reasoner"
        assert config.coder == "deepseek-chat"

        config = self.selector.select("mission-critical production fix")
        assert config.architect == "deepseek-reasoner"

    def test_default_complexity(self):
        """Неизвестная задача → medium."""
        config = self.selector.select("Совершенно случайный текст задачи")
        assert config.architect == "deepseek-chat"
        assert config.coder == "deepseek-chat"
        assert config.reviewer == "deepseek-chat"
        assert config.skip_review is False

    def test_stats(self):
        """Проверка статистики выбора."""
        selector = ModelSelector()

        selector.select("Напиши unit test")
        selector.select("Спроектируй architecture")
        selector.select("Реализуй feature")
        selector.select("Исправь critical security bug")

        stats = selector.stats
        assert stats["low"] == 1
        assert stats["high"] >= 1
        assert stats["medium"] >= 1
        assert stats["critical"] >= 1
