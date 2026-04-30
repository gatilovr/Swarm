"""Модели данных для задач и результатов."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Any


class TaskPriority(Enum):
    """Приоритет задачи. Меньшее число = выше приоритет."""
    LOW = 5
    MEDIUM = 3
    HIGH = 1
    CRITICAL = 0


class TaskStatus(Enum):
    """Статус жизненного цикла задачи."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CACHED = "cached"


@dataclass
class Task:
    """Задача для роя AI-агентов.

    Поля:
        task_id: уникальный идентификатор задачи
        content: текст технического задания
        repository: репозиторий в формате org/repo-name
        file_path: путь к файлу в репозитории
        priority: приоритет задачи
        project_profile_id: идентификатор профиля проекта
        max_cost_cents: максимальная стоимость в долларовых центах
        created_at: время создания задачи
        status: текущий статус задачи
        complexity_hint: подсказка сложности от Roo Code (auto/low/medium/high/critical)
        project_files: количество файлов в проекте (для контекста)
    """
    task_id: str
    content: str
    repository: str
    file_path: str
    priority: TaskPriority = TaskPriority.MEDIUM
    project_profile_id: Optional[str] = None
    max_cost_cents: float = 5.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    status: TaskStatus = TaskStatus.PENDING
    complexity_hint: Optional[str] = None
    project_files: int = 0

    def to_dict(self) -> dict:
        """Сериализует задачу в словарь."""
        return {
            "task_id": self.task_id,
            "content": self.content,
            "repository": self.repository,
            "file_path": self.file_path,
            "priority": self.priority.value,
            "project_profile_id": self.project_profile_id,
            "max_cost_cents": self.max_cost_cents,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "complexity_hint": self.complexity_hint,
            "project_files": self.project_files,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Task":
        """Десериализует задачу из словаря."""
        return cls(
            task_id=data["task_id"],
            content=data["content"],
            repository=data["repository"],
            file_path=data["file_path"],
            priority=TaskPriority(data.get("priority", 3)),
            project_profile_id=data.get("project_profile_id"),
            max_cost_cents=data.get("max_cost_cents", 5.0),
            created_at=datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.now(timezone.utc),
            status=TaskStatus(data.get("status", "pending")),
            complexity_hint=data.get("complexity_hint"),
            project_files=data.get("project_files", 0),
        )


@dataclass
class TaskResult:
    """Результат выполнения задачи роем.

    Поля:
        task_id: идентификатор задачи
        plan: план, созданный архитектором
        code: сгенерированный код
        review_result: результат ревью
        approved: прошла ли задача ревью
        iterations: количество итераций кодер→ревьюер
        total_tokens: общее количество потраченных токенов
        cost_usd: стоимость выполнения в долларах
        duration_sec: длительность выполнения в секундах
        cached: был ли результат взят из кэша
        error: сообщение об ошибке (если есть)
        completed_at: время завершения задачи
    """
    task_id: str
    plan: str = ""
    code: str = ""
    review_result: str = ""
    approved: bool = False
    iterations: int = 1
    total_tokens: int = 0
    cost_usd: float = 0.0
    duration_sec: float = 0.0
    cached: bool = False
    error: Optional[str] = None
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Сериализует результат в словарь."""
        return {
            "task_id": self.task_id,
            "plan": self.plan,
            "code": self.code,
            "review_result": self.review_result,
            "approved": self.approved,
            "iterations": self.iterations,
            "total_tokens": self.total_tokens,
            "cost_usd": self.cost_usd,
            "duration_sec": self.duration_sec,
            "cached": self.cached,
            "error": self.error,
            "completed_at": self.completed_at.isoformat(),
        }
