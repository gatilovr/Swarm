"""Тесты для модуля очередей (InMemoryQueue, KafkaQueue)."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from swarm_scale.queue import InMemoryQueue, KafkaQueue
from swarm_scale.task import Task, TaskPriority


class TestInMemoryQueue:
    """Тесты InMemoryQueue."""

    @pytest.fixture
    def queue(self):
        return InMemoryQueue()

    @pytest.fixture
    def sample_task(self):
        return Task(
            task_id="test-1",
            content="Напиши тест",
            repository="org/repo",
            file_path="test.py",
        )

    @pytest.mark.asyncio
    async def test_push_pop(self, queue, sample_task):
        """Добавление и извлечение задачи."""
        await queue.push(sample_task)
        result = await queue.pop()
        assert result is not None
        assert result.task_id == "test-1"
        assert result.content == "Напиши тест"

    @pytest.mark.asyncio
    async def test_pop_empty(self, queue):
        """Пустая очередь должна возвращать None."""
        result = await queue.pop()
        assert result is None

    @pytest.mark.asyncio
    async def test_acknowledge(self, queue, sample_task):
        """Подтверждение обработки задачи."""
        await queue.push(sample_task)
        await queue.pop()
        await queue.acknowledge(sample_task.task_id)
        # После acknowledge задача не должна быть в processing
        assert sample_task.task_id not in queue._processing

    @pytest.mark.asyncio
    async def test_acknowledge_unknown_id(self, queue):
        """acknowledge несуществующего ID не должен падать."""
        # Не добавляли задачу — processing пуст, acknowledge безопасен
        await queue.acknowledge("nonexistent")
        assert "nonexistent" not in queue._processing

    @pytest.mark.asyncio
    async def test_size(self, queue):
        """Корректный размер очереди."""
        assert await queue.size() == 0

        tasks = [
            Task(task_id=f"t{i}", content=f"task {i}", repository="r", file_path="f")
            for i in range(3)
        ]
        for t in tasks:
            await queue.push(t)

        assert await queue.size() == 3

        # Извлекаем одну — размер должен уменьшиться
        await queue.pop()
        assert await queue.size() == 2

    @pytest.mark.asyncio
    async def test_fifo_order(self, queue):
        """Задачи должны извлекаться в порядке FIFO."""
        tasks = [
            Task(task_id=f"t{i}", content=f"Task {i}", repository="r", file_path="f")
            for i in range(5)
        ]
        for t in tasks:
            await queue.push(t)

        for i in range(5):
            result = await queue.pop()
            assert result is not None
            assert result.task_id == f"t{i}"


class TestKafkaQueue:
    """Тесты KafkaQueue с mock'ами."""

    @pytest.fixture
    def kafka_queue(self):
        return KafkaQueue(
            bootstrap_servers="localhost:9092",
            input_topic="swarm-tasks",
            output_topic="swarm-results",
            group_id="swarm-worker",
        )

    @pytest.mark.asyncio
    async def test_push_pop_with_mock(self, kafka_queue):
        """Push и pop с mock-продюсером и консюмером."""
        sample_task = Task(
            task_id="kafka-1",
            content="Kafka task",
            repository="org/repo",
            file_path="main.py",
        )

        # Patcher для aiokafka (lazy import внутри методов)
        with patch.dict("sys.modules", {"aiokafka": MagicMock()}):
            import aiokafka
            aiokafka.AIOKafkaProducer = MagicMock(return_value=AsyncMock())
            aiokafka.AIOKafkaConsumer = MagicMock(return_value=AsyncMock())

            # Push
            await kafka_queue.push(sample_task)

            producer_instance = aiokafka.AIOKafkaProducer.return_value
            producer_instance.send.assert_called_once()
            producer_instance.start.assert_called_once()

        # Pop с mock-консюмером
        with patch.dict("sys.modules", {"aiokafka": MagicMock()}):
            import aiokafka
            mock_consumer = AsyncMock()
            # Очищаем consumer перед pop
            kafka_queue._consumer = None

            mock_msg = MagicMock()
            mock_msg.value = (
                b'{"task_id":"kafka-1","content":"Kafka task",'
                b'"repository":"org/repo","file_path":"main.py",'
                b'"priority":3,"status":"pending"}'
            )
            mock_consumer.getone = AsyncMock(return_value=mock_msg)
            aiokafka.AIOKafkaConsumer = MagicMock(return_value=mock_consumer)

            result = await kafka_queue.pop()
            assert result is not None
            assert result.task_id == "kafka-1"
            assert result.content == "Kafka task"

    @pytest.mark.asyncio
    async def test_push_error_graceful(self, kafka_queue):
        """Ошибка при push должна пробрасывать исключение."""
        with patch.dict("sys.modules", {"aiokafka": MagicMock()}):
            import aiokafka
            mock_producer = AsyncMock()
            mock_producer.send.side_effect = RuntimeError("Kafka unavailable")
            aiokafka.AIOKafkaProducer = MagicMock(return_value=mock_producer)

            task = Task(
                task_id="err-1", content="error", repository="r", file_path="f"
            )
            with pytest.raises(RuntimeError, match="Kafka unavailable"):
                await kafka_queue.push(task)

    @pytest.mark.asyncio
    async def test_pop_timeout_returns_none(self, kafka_queue):
        """При ошибке Kafka pop должен возвращать None."""
        with patch.dict("sys.modules", {"aiokafka": MagicMock()}):
            import aiokafka
            mock_consumer = AsyncMock()
            mock_consumer.getone.side_effect = RuntimeError("Connection refused")
            aiokafka.AIOKafkaConsumer = MagicMock(return_value=mock_consumer)

            result = await kafka_queue.pop()
            assert result is None

    @pytest.mark.asyncio
    async def test_size_returns_minus_one(self, kafka_queue):
        """KafkaQueue.size() должен возвращать -1."""
        size = await kafka_queue.size()
        assert size == -1

    @pytest.mark.asyncio
    async def test_acknowledge_pass(self, kafka_queue):
        """acknowledge в KafkaQueue — pass (auto-commit)."""
        await kafka_queue.acknowledge("some-id")
        # Должно пройти без ошибок
