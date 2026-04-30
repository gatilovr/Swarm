"""Тесты для RAG-контекста."""

import pytest
from swarm_scale.context import ContextBuilder, ProjectContext


class TestContextBuilder:
    """Тесты ContextBuilder."""

    def test_build_empty(self):
        """Пустой контекст."""
        builder = ContextBuilder()
        context = builder.build("org/repo")
        assert isinstance(context, ProjectContext)
        assert context.repository == "org/repo"
        assert context.files == []

    def test_add_file(self):
        """Добавление файла в контекст."""
        builder = ContextBuilder()
        builder.add_file("src/main.py", "print('hello')")
        context = builder.build("org/repo")
        assert len(context.files) == 1
        assert context.files[0]["path"] == "src/main.py"

    def test_build_with_keywords(self):
        """Контекст с ключевыми словами."""
        builder = ContextBuilder()
        builder.add_keywords("python", "async", "api")
        context = builder.build("org/repo")
        assert "python" in context.keywords
        assert len(context.keywords) == 3

    def test_context_token_count(self):
        """Подсчёт токенов в контексте."""
        builder = ContextBuilder()
        builder.add_file("test.py", "hello world " * 100)
        context = builder.build("org/repo")
        assert context.token_count > 0
