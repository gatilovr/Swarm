"""Тесты для модуля status.py — анализ состояния проекта."""

from __future__ import annotations

import os
import sys

import pytest

_SRC_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
if _SRC_PATH not in sys.path:
    sys.path.insert(0, _SRC_PATH)

from swarm_mcp.status import ProjectStatus


class TestProjectStatus:
    """Тесты ProjectStatus."""

    def test_analyze_returns_dict(self):
        """analyze() должен возвращать словарь."""
        analyzer = ProjectStatus(os.getcwd())
        result = analyzer.analyze()
        assert isinstance(result, dict)
        assert "project" in result
        assert "files" in result
        assert "structure" in result
        assert "tests" in result
        assert "git" in result
        assert "config_files" in result

    def test_summary_returns_dict(self):
        """summary() должен возвращать словарь с ключевыми метриками."""
        analyzer = ProjectStatus(os.getcwd())
        result = analyzer.summary()
        assert isinstance(result, dict)
        assert "project" in result
        assert "files_total" in result

    def test_files_count(self):
        """Должен считать файлы в проекте."""
        analyzer = ProjectStatus(os.getcwd())
        result = analyzer.analyze()
        files = result["files"]
        assert files["total"] > 0
        assert "by_type" in files
        # Должны быть .py файлы
        assert ".py" in files["by_type"]

    def test_git_status(self):
        """Должен определять git-статус."""
        analyzer = ProjectStatus(os.getcwd())
        result = analyzer.analyze()
        git = result["git"]
        assert "branch" in git
        assert "clean" in git

    def test_config_files(self):
        """Должен находить конфигурационные файлы."""
        analyzer = ProjectStatus(os.getcwd())
        result = analyzer.analyze()
        configs = result["config_files"]
        assert isinstance(configs, list)
        # В проекте должны быть .gitignore и pyproject.toml
        config_names = [c.lower() for c in configs]
        assert ".gitignore" in config_names or "pyproject.toml" in config_names

    def test_structure(self):
        """Должен возвращать структуру директорий."""
        analyzer = ProjectStatus(os.getcwd())
        result = analyzer.analyze()
        structure = result["structure"]
        assert isinstance(structure, list)
        # Должны быть директории
        dirs = [e for e in structure if e["type"] == "directory"]
        assert len(dirs) > 0

    def test_project_name(self):
        """Должен определять имя проекта."""
        analyzer = ProjectStatus(os.getcwd())
        result = analyzer.summary()
        assert len(result["project"]) > 0
