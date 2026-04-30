"""RAG-контекст для обогащения задач информацией о проекте."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProjectContext:
    """Контекст проекта для RAG-обогащения.

    Поля:
        repository: репозиторий в формате org/repo
        files: список файлов с содержимым
        keywords: ключевые слова проекта
        token_count: примерное количество токенов
    """
    repository: str
    files: list[dict] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    token_count: int = 0


class ContextBuilder:
    """Строитель RAG-контекста для задачи.

    Позволяет добавлять релевантные файлы и ключевые слова
    для обогащения промпта агентов контекстом проекта.
    """

    def __init__(self):
        self._files: list[dict] = []
        self._keywords: list[str] = []

    def add_file(self, file_path: str, content: str) -> "ContextBuilder":
        """Добавляет файл в контекст.

        Args:
            file_path: путь к файлу
            content: содержимое файла

        Returns:
            ContextBuilder: self для chaining
        """
        self._files.append({
            "path": file_path,
            "content": content,
            "tokens": len(content) // 4,  # приблизительно
        })
        return self

    def add_keywords(self, *keywords: str) -> "ContextBuilder":
        """Добавляет ключевые слова в контекст.

        Args:
            *keywords: ключевые слова

        Returns:
            ContextBuilder: self для chaining
        """
        self._keywords.extend(keywords)
        return self

    def build(self, repository: str) -> ProjectContext:
        """Строит объект ProjectContext.

        Args:
            repository: репозиторий

        Returns:
            ProjectContext: собранный контекст
        """
        total_tokens = sum(f.get("tokens", 0) for f in self._files)
        return ProjectContext(
            repository=repository,
            files=self._files,
            keywords=list(set(self._keywords)),
            token_count=total_tokens,
        )
