"""Воркер для параллельной обработки задач роем."""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from swarm import SwarmRunner

from .config import ScaleConfig
from .task import Task, TaskResult, TaskStatus
from .cache import CacheManager
from .rate_limiter import AdaptiveRateLimiter
from .model_selector import ModelSelector
from swarm.tracing import get_tracer

logger = logging.getLogger(__name__)


class SwarmWorker:
    """Воркер для масштабируемой обработки задач роем.

    Объединяет кэш, rate limiter, адаптивный выбор модели,
    параллельную обработку и OpenTelemetry tracing.

    Пример использования:
        config = ScaleConfig.from_env()
        worker = SwarmWorker(config)
        task = Task(task_id="1", content="Напиши тест", repository="org/repo", file_path="test.py")
        result = await worker.process_task(task)
    """

    def __init__(self, config: ScaleConfig):
        self.config = config
        self.cache = CacheManager(config)
        self.rate_limiter = AdaptiveRateLimiter(max_rpm=config.rpm_limit)
        self.model_selector = ModelSelector()
        self._executor = ThreadPoolExecutor(max_workers=config.max_workers)
        self._stats = {"processed": 0, "cached": 0, "errors": 0, "total_tokens": 0}
        self._tracer = get_tracer("swarm-worker")

    async def process_task(self, task: Task) -> TaskResult:
        """Обрабатывает одну задачу роем с кэшем и rate limiting.

        Args:
            task: задача для выполнения

        Returns:
            TaskResult: результат выполнения задачи
        """
        span_name = "worker.process_task"
        if self._tracer is not None:
            with self._tracer.start_as_current_span(
                span_name,
                attributes={
                    "worker.task_id": task.task_id,
                    "worker.repository": task.repository or "",
                    "worker.complexity_hint": task.complexity_hint or "auto",
                    "worker.project_files": task.project_files,
                },
            ) as span:
                result = await self._do_process_task(task, span)
                span.set_attribute("worker.success", not result.error)
                span.set_attribute("worker.cached", result.cached)
                span.set_attribute("worker.iterations", result.iterations)
                span.set_attribute("worker.duration_sec", result.duration_sec)
                return result
        else:
            return await self._do_process_task(task, None)

    async def _do_process_task(self, task: Task, span=None) -> TaskResult:
        """Внутренний метод обработки задачи с опциональным span."""
        start_time = time.time()

        # 1. Проверка кэша
        if span is not None:
            with self._tracer.start_as_current_span("worker.cache_check") as cache_span:
                cached = await self.cache.get(task, task.project_profile_id)
                cache_span.set_attribute("cache.hit", cached is not None)
        else:
            cached = await self.cache.get(task, task.project_profile_id)

        if cached:
            self._stats["cached"] += 1
            self._stats["processed"] += 1
            return TaskResult(
                task_id=task.task_id,
                cached=True,
                **cached
            )

        # 2. Выбор модели с учётом complexity_hint из Task
        force = task.complexity_hint if task.complexity_hint and task.complexity_hint != "auto" else None
        model_cfg = self.model_selector.select(task.content, force_complexity=force)
        logger.info(f"Task {task.task_id}: complexity_hint={task.complexity_hint}, force={force}, skip_review={model_cfg.skip_review}")

        # 3. Rate limiting
        if span is not None:
            with self._tracer.start_as_current_span("worker.rate_limiter"):
                await self.rate_limiter.acquire()
        else:
            await self.rate_limiter.acquire()

        # 4. Запуск роя
        try:
            # Создаём новый SwarmConfig из data-полей (без deepcopy LLM-провайдера)
            from swarm.config import SwarmConfig
            swarm_config = SwarmConfig(
                deepseek_api_key=self.config.swarm.deepseek_api_key,
                architect_model_name=self.config.swarm.architect_model_name,
                coder_model_name=self.config.swarm.coder_model_name,
                reviewer_model_name=self.config.swarm.reviewer_model_name,
                base_url=self.config.swarm.base_url,
                temperature=self.config.swarm.temperature,
                max_iterations=self.config.swarm.max_iterations,
            )
            swarm_config.architect_model_name = model_cfg.architect
            swarm_config.coder_model_name = model_cfg.coder
            if model_cfg.reviewer:
                swarm_config.reviewer_model_name = model_cfg.reviewer
            swarm_config.temperature = model_cfg.temperature

            # Запускаем SwarmRunner напрямую (теперь async)
            if span is not None:
                with self._tracer.start_as_current_span("worker.run_swarm"):
                    from swarm import SwarmRunner  # lazy import
                    runner = SwarmRunner(swarm_config)
                    final = await runner.run(task.content)
            else:
                from swarm import SwarmRunner  # lazy import
                runner = SwarmRunner(swarm_config)
                final = await runner.run(task.content)

            # Успех
            self.rate_limiter.report_success()
            self._stats["processed"] += 1

            result = TaskResult(
                task_id=task.task_id,
                plan=final.get("plan", ""),
                code=final.get("code", ""),
                review_result=final.get("review_result", ""),
                approved="APPROVED" in final.get("review_result", "").upper(),
                iterations=final.get("iteration", 1),
                duration_sec=round(time.time() - start_time, 2),
            )

            # Сохраняем в кэш
            await self.cache.set(task, {
                "plan": result.plan,
                "code": result.code,
                "review_result": result.review_result,
                "approved": result.approved,
                "iterations": result.iterations,
            }, task.project_profile_id)

            return result

        except Exception as e:
            if "429" in str(e):
                self.rate_limiter.report_429()
            self._stats["errors"] += 1
            logger.exception(f"Task {task.task_id} failed")

            return TaskResult(
                task_id=task.task_id,
                error=str(e),
                duration_sec=round(time.time() - start_time, 2),
            )

    async def process_batch(self, tasks: list[Task]) -> list[TaskResult]:
        """Параллельная обработка батча задач с семафором.

        Args:
            tasks: список задач для выполнения

        Returns:
            list[TaskResult]: список результатов выполнения
        """
        semaphore = asyncio.Semaphore(self.config.max_workers)

        async def with_semaphore(task: Task) -> TaskResult:
            async with semaphore:
                return await self.process_task(task)

        results = await asyncio.gather(
            *[with_semaphore(t) for t in tasks],
            return_exceptions=True
        )

        return [
            r if isinstance(r, TaskResult) else TaskResult(
                task_id=tasks[i].task_id,
                error=str(r),
            )
            for i, r in enumerate(results)
        ]

    @property
    def stats(self) -> dict:
        """Возвращает агрегированную статистику воркера."""
        return {
            **self._stats,
            "cache": self.cache.stats(),
            "rate_limiter": self.rate_limiter.stats,
            "model_selector": self.model_selector.stats,
        }
