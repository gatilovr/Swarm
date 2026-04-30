"""Ответы на вопросы по проекту.

Предоставляет ProjectQA, который анализирует код проекта
и отвечает на вопросы пользователя: архитектура, уязвимости,
производительность, структура.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

logger = logging.getLogger("swarm-mcp.ask")


class ProjectQA:
    """Отвечает на вопросы о проекте на основе анализа кода.

    Анализирует файловую структуру, содержимое ключевых файлов
    и возвращает структурированные ответы на вопросы пользователя.
    """

    def __init__(self, project_root: Optional[str] = None) -> None:
        """Инициализирует QA-анализатор.

        Args:
            project_root: корень проекта. Если None, используется CWD.
        """
        self.root = project_root or os.getcwd()

    async def ask(self, question: str, files: Optional[list[str]] = None) -> dict:
        """Отвечает на вопрос о проекте.

        Args:
            question: вопрос на естественном языке.
            files: опциональный список файлов для анализа (ограничение).

        Returns:
            dict: ответ с категорией и содержимым.
        """
        q_lower = question.lower().strip()

        # Определяем категорию вопроса
        category = self._categorize(q_lower)
        answer = await self._answer(category, q_lower, files)

        return {
            "question": question,
            "category": category,
            "answer": answer,
        }

    def _categorize(self, question: str) -> str:
        """Определяет категорию вопроса.

        Args:
            question: вопрос в нижнем регистре.

        Returns:
            str: категория вопроса.
        """
        categories = {
            "architecture": [
                "архитект", "структур", "как устроен", "компонент",
                "схем", "диаграм", "модул", "архитектура",
            ],
            "dependencies": [
                "зависимост", "библиотек", "пакет", "requirements",
                "pip", "npm", "pyproject", "package.json",
            ],
            "security": [
                "безопасн", "уязвим", "security", "vulnerabilit",
                "аутентифик", "авторизац", "jwt", "token", "password",
                "sql injection", "xss", "csrf",
            ],
            "performance": [
                "производительн", "быстродейств", "optimization",
                "узк", "bottleneck", "оптимизац", "speed", "slow",
            ],
            "tests": [
                "тест", "test", "покрыт", "coverage", "pytest",
                "unit test", "integration test",
            ],
            "code_quality": [
                "качеств", "code quality", "стил", "lint", "pep8",
                "лучше", "улучшить", "improve", "refactoring",
            ],
            "docs": [
                "документац", "документ", "doc", "readme", "инструкц",
                "как использовать",
            ],
            "config": [
                "конфиг", "config", "настройк", "setting", "env",
                "переменн", "variable",
            ],
        }

        for cat, keywords in categories.items():
            for kw in keywords:
                if kw in question:
                    return cat

        return "general"

    async def _answer(self, category: str, question: str, files: Optional[list[str]] = None) -> str:
        """Формирует ответ на основе категории вопроса.

        Args:
            category: категория вопроса.
            question: исходный вопрос.
            files: ограничение по файлам.

        Returns:
            str: ответ.
        """
        handlers = {
            "architecture": self._answer_architecture,
            "dependencies": self._answer_dependencies,
            "security": self._answer_security,
            "performance": self._answer_performance,
            "tests": self._answer_tests,
            "code_quality": self._answer_code_quality,
            "docs": self._answer_docs,
            "config": self._answer_config,
        }

        handler = handlers.get(category, self._answer_general)
        return await handler(question, files)

    async def _answer_architecture(self, question: str, files: Optional[list[str]] = None) -> str:
        """Анализирует архитектуру проекта."""
        structure = self._get_directory_structure()

        # Определяем основной язык/фреймворк
        main_files = self._find_main_files()
        framework = self._detect_framework()

        return (
            f"📐 Архитектура проекта\n\n"
            f"**Основной стек:** {framework}\n"
            f"**Ключевые файлы:** {', '.join(main_files[:8]) or 'не определены'}\n\n"
            f"**Структура директорий:**\n```\n{structure}\n```"
        )

    async def _answer_dependencies(self, question: str, files: Optional[list[str]] = None) -> str:
        """Анализирует зависимости проекта."""
        deps = self._read_dependencies()
        return (
            f"📦 Зависимости проекта\n\n"
            f"{deps}"
        )

    async def _answer_security(self, question: str, files: Optional[list[str]] = None) -> str:
        """Базовый анализ безопасности (без запуска инструментов)."""
        issues = self._check_security_basics()
        if not issues:
            return "🔒 Базовый анализ безопасности не выявил очевидных проблем."
        return f"⚠️ Замечены следующие моменты:\n\n" + "\n".join(f"- {i}" for i in issues)

    async def _answer_performance(self, question: str, files: Optional[list[str]] = None) -> str:
        """Анализирует возможные узкие места."""
        files_count = self._count_source_files()
        return (
            f"⚡ Производительность\n\n"
            f"**Размер проекта:** {files_count} исходных файлов\n"
            f"**Язык:** {self._detect_framework()}\n\n"
            f"Для детального профилирования используйте:\n"
            f"- Python: `python -m cProfile -s time script.py`\n"
            f"- Node.js: `node --prof app.js`\n"
        )

    async def _answer_tests(self, question: str, files: Optional[list[str]] = None) -> str:
        """Анализирует тестовое покрытие."""
        test_files = self._find_test_files()
        if not test_files:
            return "🧪 В проекте не найдены тестовые файлы."

        return (
            f"🧪 Тесты\n\n"
            f"**Найдено тестовых файлов:** {len(test_files)}\n"
            f"**Файлы:**\n"
            + "\n".join(f"- {f}" for f in test_files[:15])
            + ("\n..." if len(test_files) > 15 else "")
        )

    async def _answer_code_quality(self, question: str, files: Optional[list[str]] = None) -> str:
        """Анализирует качество кода."""
        return (
            f"🔧 Качество кода\n\n"
            f"Для проверки качества кода используйте:\n"
            f"- Python: `ruff check .` или `pylint src/`\n"
            f"- JavaScript/TS: `npx eslint .`\n"
            f"- Форматирование: `black .` (Python), `prettier .` (JS/TS)\n\n"
            f"**Рекомендация:** Добавьте pre-commit хуки для автоматической проверки."
        )

    async def _answer_docs(self, question: str, files: Optional[list[str]] = None) -> str:
        """Анализирует документацию."""
        doc_files = self._find_doc_files()
        if not doc_files:
            return "📄 В проекте не найдены файлы документации."

        return (
            f"📄 Документация\n\n"
            f"**Найденные файлы:**\n"
            + "\n".join(f"- {f}" for f in doc_files)
        )

    async def _answer_config(self, question: str, files: Optional[list[str]] = None) -> str:
        """Анализирует конфигурацию проекта."""
        configs = self._find_configs()
        if not configs:
            return "⚙️ Файлы конфигурации не найдены."

        return (
            f"⚙️ Конфигурация\n\n"
            f"**Найденные файлы:**\n"
            + "\n".join(f"- {f}" for f in configs)
        )

    async def _answer_general(self, question: str, files: Optional[list[str]] = None) -> str:
        """Общий ответ о проекте."""
        name = os.path.basename(self.root)
        structure = self._get_directory_structure(level=1)
        return (
            f"📋 Проект: {name}\n\n"
            f"**Корневая структура:**\n```\n{structure}\n```\n\n"
            f"Чтобы узнать подробнее, спросите:\n"
            f"- 'Какая архитектура проекта?'\n"
            f"- 'Какие есть зависимости?'\n"
            f"- 'Есть ли тесты?'\n"
        )

    def _get_directory_structure(self, level: int = 2) -> str:
        """Возвращает структуру директорий в виде дерева."""
        lines = []
        root_name = os.path.basename(self.root)
        lines.append(f"{root_name}/")

        def walk(dirpath: str, prefix: str = "", depth: int = 0) -> None:
            if depth >= level:
                return
            try:
                entries = sorted([
                    e for e in os.listdir(dirpath)
                    if not e.startswith(".") and e not in ("node_modules", "__pycache__")
                ])
            except PermissionError:
                return

            for i, entry in enumerate(entries):
                is_last = i == len(entries) - 1
                connector = "└── " if is_last else "├── "
                fpath = os.path.join(dirpath, entry)
                if os.path.isdir(fpath):
                    lines.append(f"{prefix}{connector}{entry}/")
                    walk(fpath, f"{prefix}{'    ' if is_last else '│   '}", depth + 1)
                else:
                    lines.append(f"{prefix}{connector}{entry}")

        walk(self.root, "", 1)
        return "\n".join(lines)

    def _find_main_files(self) -> list[str]:
        """Находит основные файлы проекта."""
        patterns = [
            "main.py", "app.py", "index.py", "cli.py",
            "server.py", "app.js", "index.js", "index.ts",
        ]
        found = []
        for pattern in patterns:
            fpath = os.path.join(self.root, pattern)
            if os.path.exists(fpath):
                found.append(pattern)
        return found

    def _detect_framework(self) -> str:
        """Определяет основной стек технологий."""
        stack = []

        # Python
        if os.path.exists(os.path.join(self.root, "pyproject.toml")):
            stack.append("Python")
            # Проверка на FastAPI/Django/Flask
            with open(os.path.join(self.root, "pyproject.toml"), "r", encoding="utf-8") as f:
                content = f.read()
                if "fastapi" in content.lower():
                    stack.append("FastAPI")
                elif "django" in content.lower():
                    stack.append("Django")
                elif "flask" in content.lower():
                    stack.append("Flask")

        # Node.js
        if os.path.exists(os.path.join(self.root, "package.json")):
            stack.append("Node.js")
            try:
                import json
                with open(os.path.join(self.root, "package.json"), "r", encoding="utf-8") as f:
                    pkg = json.load(f)
                    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                    if "react" in deps:
                        stack.append("React")
                    if "vue" in deps:
                        stack.append("Vue.js")
                    if "express" in deps:
                        stack.append("Express")
            except Exception:
                pass

        # TypeScript
        if os.path.exists(os.path.join(self.root, "tsconfig.json")):
            stack.append("TypeScript")

        return " + ".join(stack) if stack else "не удалось определить"

    def _read_dependencies(self) -> str:
        """Читает файлы зависимостей."""
        parts = []

        # pyproject.toml
        pyproject = os.path.join(self.root, "pyproject.toml")
        if os.path.exists(pyproject):
            try:
                with open(pyproject, "r", encoding="utf-8") as f:
                    content = f.read()
                # Вытаскиваем секцию dependencies
                match = re.search(r"\[project\](.*?)(?=\[|$)", content, re.DOTALL)
                if match:
                    parts.append(f"**Python (pyproject.toml):**\n```\n{match.group(1).strip()[:500]}\n```")
            except Exception:
                pass

        # requirements.txt
        req = os.path.join(self.root, "requirements.txt")
        if os.path.exists(req):
            try:
                with open(req, "r", encoding="utf-8") as f:
                    content = f.read()
                parts.append(f"**Python (requirements.txt):**\n```\n{content[:500]}\n```")
            except Exception:
                pass

        # package.json
        pkg = os.path.join(self.root, "package.json")
        if os.path.exists(pkg):
            try:
                import json
                with open(pkg, "r", encoding="utf-8") as f:
                    data = json.load(f)
                deps = data.get("dependencies", {})
                dev_deps = data.get("devDependencies", {})
                lines = [f"- {k}: {v}" for k, v in deps.items()]
                lines += [f"- [{k} (dev)]: {v}" for k, v in dev_deps.items()]
                parts.append(f"**Node.js (package.json):** {len(deps)} deps, {len(dev_deps)} devDeps\n" + "\n".join(lines[:20]))
            except Exception:
                pass

        return "\n\n".join(parts) if parts else "Файлы зависимостей не найдены."

    _MAX_SCAN_FILES = 200  # Максимум файлов для сканирования безопасности

    def _check_security_basics(self) -> list[str]:
        """Базовый поиск потенциальных проблем безопасности (макс. _MAX_SCAN_FILES файлов)."""
        issues = []
        patterns = {
            "API key hardcoded": [r'api_key\s*=\s*["\'][^"\']+["\']', r'API_KEY\s*=\s*["\'][^"\']+["\']'],
            "Password hardcoded": [r'password\s*=\s*["\'][^"\']+["\']'],
            "Secret hardcoded": [r'secret\s*=\s*["\'][^"\']+["\']', r'SECRET_KEY\s*=\s*["\'][^"\']+["\']'],
            "eval() usage": [r'\beval\s*\('],
            "exec() usage": [r'\bexec\s*\('],
            "subprocess with shell=True": [r'subprocess\.\w+\(.*shell\s*=\s*True'],
        }

        scanned = 0
        for dirpath, _, filenames in os.walk(self.root):
            if any(skip in dirpath for skip in (".git", "node_modules", "__pycache__", ".venv")):
                continue
            for fname in filenames:
                if scanned >= self._MAX_SCAN_FILES:
                    logger.info(f"Security scan stopped after {self._MAX_SCAN_FILES} files")
                    return list(set(issues))
                if fname.endswith((".py", ".js", ".ts", ".jsx", ".tsx")):
                    scanned += 1
                    fpath = os.path.join(dirpath, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()
                        for issue_name, patterns_list in patterns.items():
                            for pattern in patterns_list:
                                if re.search(pattern, content):
                                    rel_path = os.path.relpath(fpath, self.root)
                                    issues.append(f"{issue_name} in {rel_path}")
                                    break
                    except Exception:
                        pass

        return list(set(issues))  # Убираем дубликаты

    def _count_source_files(self) -> int:
        """Считает количество исходных файлов."""
        count = 0
        for dirpath, _, filenames in os.walk(self.root):
            if any(skip in dirpath for skip in (".git", "node_modules", "__pycache__")):
                continue
            for fname in filenames:
                if fname.endswith((".py", ".js", ".ts", ".jsx", ".tsx", ".html", ".css", ".json")):
                    count += 1
        return count

    def _find_test_files(self) -> list[str]:
        """Находит тестовые файлы."""
        test_files = []
        for dirpath, _, filenames in os.walk(self.root):
            if ".git" in dirpath or "node_modules" in dirpath:
                continue
            for fname in filenames:
                if fname.startswith("test_") or fname.endswith("_test.py") or fname.endswith(".test.js"):
                    test_files.append(os.path.relpath(os.path.join(dirpath, fname), self.root))
        return sorted(test_files)

    def _find_doc_files(self) -> list[str]:
        """Находит файлы документации."""
        doc_files = []
        patterns = ["*.md", "*.rst", "*.txt", "docs/*"]
        for dirpath, _, filenames in os.walk(self.root):
            if ".git" in dirpath:
                continue
            for fname in filenames:
                if fname.lower() in ("readme.md", "readme.rst", "contributing.md", "changelog.md"):
                    doc_files.append(os.path.relpath(os.path.join(dirpath, fname), self.root))
                elif fname.endswith((".md", ".rst")) and "docs" in dirpath.lower():
                    doc_files.append(os.path.relpath(os.path.join(dirpath, fname), self.root))
        return sorted(doc_files)

    def _find_configs(self) -> list[str]:
        """Находит конфигурационные файлы."""
        configs = []
        patterns = [
            ".env", ".env.example", ".env.sample",
            "pyproject.toml", "package.json", "tsconfig.json",
            ".eslintrc", ".prettierrc", ".flake8", "ruff.toml",
            ".github/workflows", "docker-compose.yml", "Dockerfile",
            ".gitignore", ".swarm-policy.toml",
        ]
        for pattern in patterns:
            fpath = os.path.join(self.root, pattern)
            if os.path.exists(fpath):
                configs.append(pattern)
        return sorted(configs)
