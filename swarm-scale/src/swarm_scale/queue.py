"""Абстракция очереди задач (InMemory, Kafka, Redis)."""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

from .task import Task

logger = logging.getLogger(__name__)


class TaskQueue(ABC):
    """Абстрактная очередь задач."""

    @abstractmethod
    async def push(self, task: Task) -> None:
        """Добавляет задачу в очередь."""
        ...

    @abstractmethod
    async def pop(self) -> Optional[Task]:
        """Извлекает задачу из очереди."""
        ...

    @abstractmethod
    async def acknowledge(self, task_id: str) -> None:
        """Подтверждает обработку задачи."""
        ...

    @abstractmethod
    async def size(self) -> int:
        """Возвращает размер очереди."""
        ...


class InMemoryQueue(TaskQueue):
    """In-memory очередь для разработки и тестов."""

    def __init__(self):
        self._queue: asyncio.Queue[Task] = asyncio.Queue()
        self._processing: set[str] = set()

    async def push(self, task: Task) -> None:
        """Добавляет задачу в очередь."""
        await self._queue.put(task)
        logger.debug(f"Task {task.task_id} pushed to in-memory queue")

    async def pop(self) -> Optional[Task]:
        """Извлекает задачу из очереди."""
        try:
            task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            self._processing.add(task.task_id)
            return task
        except asyncio.TimeoutError:
            return None

    async def acknowledge(self, task_id: str) -> None:
        """Подтверждает обработку задачи."""
        if task_id in self._processing:
            self._processing.discard(task_id)

    async def size(self) -> int:
        """Возвращает размер очереди."""
        return self._queue.qsize()


class KafkaQueue(TaskQueue):
    """Очередь на основе Kafka.

    Использует топик ``input_topic`` для входящих задач и
    ``output_topic`` для результатов. Потребление основано на
    Kafka consumer groups — auto-commit включён по умолчанию,
    поэтому ``acknowledge`` не требует ручного confirmation offset.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        input_topic: str = "swarm-tasks",
        output_topic: str = "swarm-results",
        group_id: str = "swarm-worker",
    ):
        """Инициализирует KafkaQueue.

        Args:
            bootstrap_servers: адреса Kafka брокеров (host:port, через запятую).
            input_topic: Kafka топик для входящих задач (по умолчанию ``swarm-tasks``).
            output_topic: Kafka топик для результатов (по умолчанию ``swarm-results``).
            group_id: идентификатор consumer group (по умолчанию ``swarm-worker``).
                      Auto-commit offset включён на уровне ``AIOKafkaConsumer``.
        """
        self._bootstrap_servers = bootstrap_servers
        self._input_topic = input_topic
        self._output_topic = output_topic
        self._group_id = group_id
        self._producer = None
        self._consumer = None

    async def push(self, task: Task) -> None:
        """Добавляет задачу в Kafka топик.

        Сериализует ``Task`` в JSON и отправляет сообщение
        в ``input_topic`` через ``AIOKafkaProducer``.

        Формат сообщения:
            {
                "task_id": "...",
                "content": "...",
                "repository": "...",
                "file_path": "..."
            }

        Args:
            task: задача для отправки.

        Raises:
            Exception: при ошибке подключения или отправки.
        """
        try:
            from aiokafka import AIOKafkaProducer
            if self._producer is None:
                self._producer = AIOKafkaProducer(
                    bootstrap_servers=self._bootstrap_servers,
                )
                await self._producer.start()

            await self._producer.send(
                self._input_topic,
                json.dumps(task.to_dict()).encode(),
            )
        except Exception as e:
            logger.error(f"Kafka push error: {e}")
            raise

    async def pop(self) -> Optional[Task]:
        """Извлекает задачу из Kafka топика.

        Читает следующее сообщение из ``input_topic`` через
        ``AIOKafkaConsumer`` с ``auto_offset_reset="earliest"``.
        Десериализует JSON обратно в ``Task``.

        Returns:
            Optional[Task]: задача или ``None`` при ошибке/таймауте.
        """
        try:
            from aiokafka import AIOKafkaConsumer
            if self._consumer is None:
                self._consumer = AIOKafkaConsumer(
                    self._input_topic,
                    bootstrap_servers=self._bootstrap_servers,
                    group_id=self._group_id,
                    auto_offset_reset="earliest",
                )
                await self._consumer.start()

            msg = await self._consumer.getone()
            data = json.loads(msg.value.decode())
            return Task.from_dict(data)
        except Exception as e:
            logger.error(f"Kafka pop error: {e}")
            return None

    async def acknowledge(self, task_id: str) -> None:
        """Подтверждает обработку задачи.

        В текущей реализации Kafka consumer работает с auto-commit,
        поэтому явное подтверждение смещения не требуется — метод
        является заглушкой для совместимости с интерфейсом ``TaskQueue``.

        Args:
            task_id: идентификатор задачи (не используется).
        """
        pass

    async def size(self) -> int:
        """Возвращает размер очереди."""
        return -1  # Kafka не предоставляет точного размера
