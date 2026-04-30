"""Анализ состояния проекта.

Предоставляет ProjectStatus для сбора информации о текущем
состоянии проекта: количество файлов, тесты, структура.
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Optional

logger = logging.getLogger("swarm-mcp.status")


class ProjectStatus:
    """Анализирует состояние проекта.

    Собирает информацию о файловой структуре, тестах, git-статусе
    и другой полезной метрике для мониторинга проекта.
    """

    def __init__(self, project_root: Optional[str] = None) -> None:
        """Инициализирует анализатор состояния.

        Args:
            project_root: корень проекта. Если None, используется CWD.
        """
        self.root = project_root or os.getcwd()

    def analyze(self) -> dict:
        """Анализирует текущее состояние проекта.

        Returns:
            dict: словарь с метриками проекта.
        """
        return {
            "project": self._get_project_name(),
            "files": self._count_files(),
            "structure": self._get_structure(),
            "tests": self._check_tests(),
            "git": self._git_status(),
            "config_files": self._find_config_files(),
        }

    def summary(self) -> dict:
        """Краткая сводка (для swarm_status без scope='full').

        Returns:
            dict: краткая сводка проекта.
        """
        files = self._count_files()
        tests = self._check_tests()
        git = self._git_status()

        return {
            "project": self._get_project_name(),
            "files_total": files.get("total", 0),
            "files_by_type": files.get("by_type", {}),
            "tests": tests,
            "git_branch": git.get("branch", "unknown"),
            "git_clean": git.get("clean", True),
        }

    def _get_project_name(self) -> str:
        """Определяет имя проекта из корневой директории."""
        try:
            # Попытка прочитать из pyproject.toml
            pyproject_path = os.path.join(self.root, "pyproject.toml")
            if os.path.exists(pyproject_path):
                with open(pyproject_path, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip().startswith("name"):
                            return line.split("=")[-1].strip().strip('"').strip("'")
        except Exception:
            pass
        return os.path.basename(self.root)

    def _count_files(self) -> dict:
        """Считает файлы в проекте по расширениям."""
        total = 0
        by_type: dict[str, int] = {}
        total_lines = 0

        for dirpath, dirnames, filenames in os.walk(self.root):
            # Исключаем скрытые и виртуальные окружения
            dirnames[:] = [
                d for d in dirnames
                if not d.startswith(".") and d not in ("node_modules", "__pycache__", "venv", ".venv")
            ]

            for fname in filenames:
                ext = os.path.splitext(fname)[1] or "(no ext)"
                by_type[ext] = by_type.get(ext, 0) + 1
                total += 1

                try:
                    fpath = os.path.join(dirpath, fname)
                    with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                        total_lines += sum(1 for _ in f)
                except Exception:
                    pass

        return {
            "total": total,
            "by_type": dict(sorted(by_type.items(), key=lambda x: -x[1])),
            "total_lines": total_lines,
        }

    def _get_structure(self) -> list[dict]:
        """Возвращает структуру директорий первого уровня."""
        entries = []
        try:
            for entry in sorted(os.listdir(self.root)):
                if entry.startswith("."):
                    continue
                fpath = os.path.join(self.root, entry)
                entries.append({
                    "name": entry,
                    "type": "directory" if os.path.isdir(fpath) else "file",
                })
        except Exception:
            pass
        return entries

    def _check_tests(self) -> dict:
        """Проверяет статус тестов (без запуска)."""
        test_dirs = []
        test_files = []

        for dirpath, _, filenames in os.walk(self.root):
            if "test" in dirpath.lower() or "tests" in dirpath.lower():
                if dirpath != self.root:
                    test_dirs.append(os.path.relpath(dirpath, self.root))
                for fname in filenames:
                    if fname.startswith("test_") or fname.endswith("_test.py"):
                        test_files.append(os.path.relpath(
                            os.path.join(dirpath, fname), self.root
                        ))

        return {
            "test_directories": len(test_dirs),
            "test_files": len(test_files),
            "test_file_list": test_files[:20],  # первые 20
        }

    def _git_status(self) -> dict:
        """Проверяет git-статус проекта."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain", "--branch"],
                capture_output=True,
                text=True,
                cwd=self.root,
                timeout=10,
            )
            lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
            branch = "unknown"
            clean = True
            modified = 0
            staged = 0

            for line in lines:
                if line.startswith("##"):
                    branch = line.split(" ")[0].replace("## ", "")
                elif line.startswith("??"):
                    clean = False
                elif line.strip():
                    if line.startswith("M") or line.startswith("A") or line.startswith("D"):
                        staged += 1
                    else:
                        modified += 1
                    clean = False

            # Коммиты впереди/позади
            ahead, behind = 0, 0
            if branch:
                try:
                    branch_result = subprocess.run(
                        ["git", "rev-list", "--count", f"origin/{branch}..{branch}"],
                        capture_output=True,
                        text=True,
                        cwd=self.root,
                        timeout=10,
                    )
                    ahead = int(branch_result.stdout.strip() or 0)

                    behind_result = subprocess.run(
                        ["git", "rev-list", "--count", f"{branch}..origin/{branch}"],
                        capture_output=True,
                        text=True,
                        cwd=self.root,
                        timeout=10,
                    )
                    behind = int(behind_result.stdout.strip() or 0)
                except Exception:
                    pass

            return {
                "branch": branch,
                "clean": clean,
                "modified": modified,
                "staged": staged,
                "ahead": ahead,
                "behind": behind,
            }
        except Exception as e:
            return {
                "branch": "error",
                "clean": False,
                "error": str(e),
            }

    def _find_config_files(self) -> list[str]:
        """Находит конфигурационные файлы проекта."""
        config_patterns = [
            ".env",
            ".env.example",
            "pyproject.toml",
            "package.json",
            "tsconfig.json",
            "Dockerfile",
            "docker-compose.yml",
            ".github/workflows",
            ".gitignore",
            ".swarm-policy.toml",
        ]
        found = []
        for pattern in config_patterns:
            fpath = os.path.join(self.root, pattern)
            if os.path.exists(fpath):
                found.append(pattern)
        return found
