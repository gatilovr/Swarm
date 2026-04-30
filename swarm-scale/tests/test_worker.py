"""Тесты для воркера."""

from unittest.mock import patch, MagicMock, AsyncMock
import pytest

from swarm_scale.worker import SwarmWorker
from swarm_scale.task import Task, TaskResult, TaskStatus
from swarm_scale.config import ScaleConfig


class TestSwarmWorker:
    """Тесты SwarmWorker."""

    @pytest.fixture
    def config(self):
        from swarm.config import SwarmConfig
        cfg = ScaleConfig()
        cfg.swarm = SwarmConfig()
        return cfg

    @pytest.fixture
    def worker(self, config):
        return SwarmWorker(config)

    @pytest.mark.asyncio
    async def test_process_task(self, worker):
        """Полный цикл обработки задачи с mock'ом роя."""
        task = Task(
            task_id="test-1",
            content="Напиши функцию сортировки",
            repository="org/repo",
            file_path="test.py",
        )

        # Мокаем SwarmRunner.run() — теперь async
        mock_final = {
            "plan": "1. Создать файл теста",
            "code": "def test_func(): pass",
            "review_result": "APPROVED",
            "iteration": 1,
        }

        with patch("swarm.SwarmRunner") as MockRunner:
            mock_instance = MagicMock()
            mock_instance.run = AsyncMock(return_value=mock_final)
            MockRunner.return_value = mock_instance

            result = await worker.process_task(task)

        assert isinstance(result, TaskResult)
        assert result.task_id == "test-1"
        assert result.plan == "1. Создать файл теста"
        assert result.code == "def test_func(): pass"
        assert result.approved is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_process_task_cached(self, worker):
        """Проверка использования кэша."""
        task = Task(
            task_id="test-2",
            content="Напиши тест для кэша",
            repository="org/repo",
            file_path="test.py",
        )

        # Сначала кладём в кэш
        cached_data = {
            "plan": "Cached plan",
            "code": "cached code",
            "review_result": "APPROVED",
            "approved": True,
            "iterations": 1,
        }
        await worker.cache.set(task, cached_data, task.project_profile_id)

        # Обрабатываем — должен взять из кэша
        with patch("swarm.SwarmRunner") as MockRunner:
            result = await worker.process_task(task)

        assert result.cached is True
        assert result.plan == "Cached plan"
        assert result.code == "cached code"
        # Убеждаемся, что SwarmRunner не вызывался
        MockRunner.assert_not_called()

    @pytest.mark.asyncio
    async def test_process_task_error(self, worker):
        """Обработка ошибки при выполнении задачи."""
        task = Task(
            task_id="test-3",
            content="Сломай всё",
            repository="org/repo",
            file_path="crash.py",
        )

        with patch("swarm.SwarmRunner") as MockRunner:
            mock_instance = MagicMock()
            mock_instance.run = AsyncMock(side_effect=RuntimeError("API error"))
            MockRunner.return_value = mock_instance

            result = await worker.process_task(task)

        assert isinstance(result, TaskResult)
        assert result.task_id == "test-3"
        assert result.error is not None
        assert "API error" in result.error

    @pytest.mark.asyncio
    async def test_process_batch(self, worker):
        """Параллельная обработка батча задач."""
        tasks = [
            Task(
                task_id=f"batch-{i}",
                content=f"Задача {i}",
                repository="org/repo",
                file_path=f"file{i}.py",
            )
            for i in range(3)
        ]

        mock_final = {
            "plan": "test plan",
            "code": "test code",
            "review_result": "APPROVED",
            "iteration": 1,
        }

        with patch("swarm.SwarmRunner") as MockRunner:
            mock_instance = MagicMock()
            mock_instance.run = AsyncMock(return_value=mock_final)
            MockRunner.return_value = mock_instance

            results = await worker.process_batch(tasks)

        assert len(results) == 3
        for i, result in enumerate(results):
            assert isinstance(result, TaskResult)
            assert result.task_id == f"batch-{i}"
            assert result.error is None

    @pytest.mark.asyncio
    async def test_worker_stats(self, worker):
        """Проверка агрегированной статистики."""
        stats = worker.stats
        assert "processed" in stats
        assert "cached" in stats
        assert "errors" in stats
        assert "cache" in stats
        assert "rate_limiter" in stats
        assert "model_selector" in stats
