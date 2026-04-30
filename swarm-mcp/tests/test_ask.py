"""Тесты для модуля ask.py — вопросы по проекту."""

from __future__ import annotations

import os
import sys

import pytest

_SRC_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

from swarm_mcp.ask import ProjectQA


class TestProjectQA:
    """Тесты ProjectQA."""

    @pytest.mark.asyncio
    async def test_ask_about_architecture(self):
        """Вопрос об архитектуре должен возвращать категорию 'architecture'."""
        qa = ProjectQA(os.getcwd())
        result = await qa.ask("Какая архитектура проекта?")
        assert result["category"] == "architecture"
        assert len(result["answer"]) > 0

    @pytest.mark.asyncio
    async def test_ask_about_security(self):
        """Вопрос о безопасности должен возвращать категорию 'security'."""
        qa = ProjectQA(os.getcwd())
        result = await qa.ask("Есть ли уязвимости?")
        assert result["category"] == "security"
        assert len(result["answer"]) > 0

    @pytest.mark.asyncio
    async def test_ask_about_dependencies(self):
        """Вопрос о зависимостях должен возвращать категорию 'dependencies'."""
        qa = ProjectQA(os.getcwd())
        result = await qa.ask("Какие библиотеки используются?")
        assert result["category"] == "dependencies"
        assert len(result["answer"]) > 0

    @pytest.mark.asyncio
    async def test_ask_about_tests(self):
        """Вопрос о тестах должен возвращать категорию 'tests'."""
        qa = ProjectQA(os.getcwd())
        result = await qa.ask("Какие есть тесты?")
        assert result["category"] == "tests"
        assert len(result["answer"]) > 0

    @pytest.mark.asyncio
    async def test_ask_about_performance(self):
        """Вопрос о производительности должен возвращать категорию 'performance'."""
        qa = ProjectQA(os.getcwd())
        result = await qa.ask("Где узкое место?")
        assert result["category"] == "performance"
        assert len(result["answer"]) > 0

    @pytest.mark.asyncio
    async def test_ask_about_code_quality(self):
        """Вопрос о качестве кода должен возвращать категорию 'code_quality'."""
        qa = ProjectQA(os.getcwd())
        result = await qa.ask("Как улучшить код?")
        assert result["category"] == "code_quality"
        assert len(result["answer"]) > 0

    @pytest.mark.asyncio
    async def test_ask_about_docs(self):
        """Вопрос о документации должен возвращать категорию 'docs'."""
        qa = ProjectQA(os.getcwd())
        result = await qa.ask("Есть ли документация?")
        assert result["category"] == "docs"
        assert len(result["answer"]) > 0

    @pytest.mark.asyncio
    async def test_ask_about_config(self):
        """Вопрос о конфигурации должен возвращать категорию 'config'."""
        qa = ProjectQA(os.getcwd())
        result = await qa.ask("Какие настройки?")
        assert result["category"] == "config"
        assert len(result["answer"]) > 0

    @pytest.mark.asyncio
    async def test_general_question(self):
        """Общий вопрос должен возвращать категорию 'general'."""
        qa = ProjectQA(os.getcwd())
        result = await qa.ask("Что это за проект?")
        assert result["category"] == "general"
        assert len(result["answer"]) > 0

    @pytest.mark.asyncio
    async def test_answer_contains_project_info(self):
        """Ответ должен содержать информацию о проекте."""
        qa = ProjectQA(os.getcwd())
        result = await qa.ask("Какая архитектура?")
        answer = result["answer"]
        assert "Проект:" in answer or "архитектура" in answer.lower()
