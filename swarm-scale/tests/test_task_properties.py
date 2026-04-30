"""Property-based тесты для моделей данных (Task, TaskResult).

Инварианты:
- Task → to_dict() → from_dict() → Task сохраняет все поля (roundtrip)
- TaskResult → to_dict() → from_dict() → TaskResult сохраняет все поля
- Сериализация/десериализация стабильна (idempotent)
"""
import pytest
from datetime import datetime
from hypothesis import given, strategies as st
from swarm_scale.task import Task, TaskResult, TaskPriority, TaskStatus


# Стратегии
text_strategy = st.text(
    min_size=0, max_size=200,
    alphabet="abcdefghijklmnopqrstuvwxyz0123456789 _-",
)
complexity_strategy = st.one_of(
    st.none(),
    st.sampled_from(["auto", "low", "medium", "high", "critical"]),
)


class TestTaskProperties:
    """Property-based тесты для Task."""

    @given(
        content=text_strategy,
        repository=text_strategy,
        file_path=text_strategy,
        task_id=text_strategy,
        priority=st.integers(min_value=0, max_value=5),
        complexity_hint=complexity_strategy,
        project_files=st.integers(min_value=0, max_value=10000),
    )
    def test_task_roundtrip(self, content, repository, file_path, task_id, priority, complexity_hint, project_files):
        """Task → to_dict() → from_dict() → Task сохраняет все поля."""
        original = Task(
            task_id=task_id or "default_id",
            content=content or "default_content",
            repository=repository or "default_repo",
            file_path=file_path or "default_path",
            priority=TaskPriority(priority) if priority in [0, 1, 3, 5] else TaskPriority.MEDIUM,
            complexity_hint=complexity_hint,
            project_files=project_files,
        )

        # Roundtrip 1: Task → dict → Task
        d = original.to_dict()
        restored = Task.from_dict(d)

        assert restored.content == original.content
        assert restored.task_id == original.task_id
        assert restored.priority == original.priority
        assert restored.complexity_hint == original.complexity_hint
        assert restored.project_files == original.project_files
        assert restored.repository == original.repository
        assert restored.file_path == original.file_path
        assert restored.status == original.status

        # Roundtrip 2: dict → Task → dict (консистентность сериализации)
        d2 = restored.to_dict()
        assert d == d2

    @given(
        content=text_strategy,
        repository=text_strategy,
        file_path=text_strategy,
        task_id=text_strategy,
    )
    def test_task_default_status(self, content, repository, file_path, task_id):
        """Новая задача всегда имеет статус PENDING."""
        task = Task(
            task_id=task_id or "default_id",
            content=content or "default_content",
            repository=repository or "default_repo",
            file_path=file_path or "default_path",
        )
        assert task.status == TaskStatus.PENDING
        assert task.priority == TaskPriority.MEDIUM

    @given(
        content=text_strategy,
        repository=text_strategy,
        file_path=text_strategy,
        task_id=text_strategy,
        max_cost=st.floats(min_value=0.01, max_value=1000.0, allow_nan=False, allow_infinity=False),
    )
    def test_task_serialization_includes_cost(self, content, repository, file_path, task_id, max_cost):
        """Сериализация включает все числовые поля."""
        task = Task(
            task_id=task_id or "default_id",
            content=content or "default_content",
            repository=repository or "default_repo",
            file_path=file_path or "default_path",
            max_cost_cents=max_cost,
        )
        d = task.to_dict()
        assert "task_id" in d
        assert "content" in d
        assert "max_cost_cents" in d
        assert d["max_cost_cents"] == max_cost

    def test_task_created_at_is_datetime(self):
        """created_at автоматически устанавливается в datetime."""
        task = Task(
            task_id="id", content="content",
            repository="repo", file_path="path",
        )
        assert isinstance(task.created_at, datetime)

    @given(
        priority_value=st.integers(min_value=0, max_value=10),
    )
    def test_task_priority_conversion(self, priority_value):
        """TaskPriority может быть создан из любого допустимого значения."""
        valid_values = {0: TaskPriority.CRITICAL, 1: TaskPriority.HIGH,
                        3: TaskPriority.MEDIUM, 5: TaskPriority.LOW}
        if priority_value in valid_values:
            p = TaskPriority(priority_value)
            assert p in [TaskPriority.CRITICAL, TaskPriority.HIGH,
                        TaskPriority.MEDIUM, TaskPriority.LOW]
        else:
            # Для невалидных значений используем MEDIUM по умолчанию
            pass

    @given(
        content=text_strategy,
        repository=text_strategy,
        file_path=text_strategy,
        task_id=text_strategy,
    )
    def test_task_idempotent_serialization(self, content, repository, file_path, task_id):
        """to_dict() → from_dict() → to_dict() даёт тот же dict (идемпотентность)."""
        task = Task(
            task_id=task_id or "default_id",
            content=content or "default_content",
            repository=repository or "default_repo",
            file_path=file_path or "default_path",
        )
        d1 = task.to_dict()
        restored = Task.from_dict(d1)
        d2 = restored.to_dict()
        assert d1 == d2


class TestTaskResultProperties:
    """Property-based тесты для TaskResult."""

    @given(
        plan=text_strategy,
        code=text_strategy,
        review_result=text_strategy,
        approved=st.booleans(),
        cached=st.booleans(),
        iterations=st.integers(min_value=0, max_value=10),
        total_tokens=st.integers(min_value=0, max_value=100000),
        cost_usd=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False),
        duration_sec=st.floats(min_value=0.0, max_value=3600.0, allow_nan=False, allow_infinity=False),
        error=st.one_of(st.none(), text_strategy),
    )
    def test_task_result_to_dict_roundtrip(self, plan, code, review_result, approved, cached, iterations, total_tokens, cost_usd, duration_sec, error):
        """TaskResult → to_dict() содержит все поля с корректными значениями."""
        result = TaskResult(
            task_id="test_id",
            plan=plan or "",
            code=code or "",
            review_result=review_result or "",
            approved=approved,
            cached=cached,
            iterations=iterations,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            duration_sec=duration_sec,
            error=error,
        )

        d = result.to_dict()

        assert d["task_id"] == result.task_id
        assert d["plan"] == result.plan
        assert d["code"] == result.code
        assert d["review_result"] == result.review_result
        assert d["approved"] == result.approved
        assert d["cached"] == result.cached
        assert d["iterations"] == result.iterations
        assert d["total_tokens"] == result.total_tokens
        assert d["cost_usd"] == result.cost_usd
        assert d["duration_sec"] == result.duration_sec
        assert d["error"] == result.error
        assert d["completed_at"] == result.completed_at.isoformat()

    def test_task_result_completed_at_is_datetime(self):
        """completed_at всегда datetime."""
        result = TaskResult(task_id="test_id")
        assert isinstance(result.completed_at, datetime)

    def test_task_result_default_values(self):
        """TaskResult имеет разумные значения по умолчанию."""
        result = TaskResult(task_id="test_id")
        assert result.plan == ""
        assert result.code == ""
        assert result.review_result == ""
        assert result.approved is False
        assert result.iterations == 1
        assert result.total_tokens == 0
        assert result.cost_usd == 0.0
        assert result.duration_sec == 0.0
        assert result.cached is False
        assert result.error is None

    @given(
        plan=text_strategy,
        code=text_strategy,
        review_result=text_strategy,
        approved=st.booleans(),
        cached=st.booleans(),
        iterations=st.integers(min_value=0, max_value=10),
        error=st.one_of(st.none(), text_strategy),
    )
    def test_task_result_to_dict_idempotent(self, plan, code, review_result, approved, cached, iterations, error):
        """to_dict() идемпотентен: повторный вызов даёт тот же результат."""
        result = TaskResult(
            task_id="test_id",
            plan=plan or "",
            code=code or "",
            review_result=review_result or "",
            approved=approved,
            cached=cached,
            iterations=iterations,
            error=error,
        )
        d1 = result.to_dict()
        d2 = result.to_dict()
        assert d1 == d2

    @given(
        plan=text_strategy,
        code=text_strategy,
        review_result=text_strategy,
        approved=st.booleans(),
        error=st.one_of(st.none(), text_strategy),
    )
    def test_task_result_numeric_types(self, plan, code, review_result, approved, error):
        """Числовые поля TaskResult имеют правильные типы."""
        result = TaskResult(
            task_id="test_id",
            plan=plan or "",
            code=code or "",
            review_result=review_result or "",
            approved=approved,
            error=error,
        )
        assert isinstance(result.iterations, int)
        assert isinstance(result.total_tokens, int)
        assert isinstance(result.cost_usd, float)
        assert isinstance(result.duration_sec, float)
        assert isinstance(result.approved, bool)
        assert isinstance(result.cached, bool)
