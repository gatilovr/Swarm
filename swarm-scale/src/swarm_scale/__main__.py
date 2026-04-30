"""CLI entry point: python -m swarm_scale

Режимы:
    python -m swarm_scale task <text>              # одна задача
    python -m swarm_scale batch <file>             # батч из JSON
    python -m swarm_scale worker --queue memory    # daemon-воркер
"""

import argparse
import asyncio
import json
import logging
import os
import signal
import sys
from pathlib import Path
from typing import Optional


def _setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def _load_config(config_path: Optional[str] = None):
    """Загружает ScaleConfig, опционально из указанного .env файла."""
    from swarm_scale.config import ScaleConfig

    if config_path:
        return ScaleConfig.from_env(config_path)
    return ScaleConfig()


# --------------------------------------------------------------------------- #
# Режим: одна задача
# --------------------------------------------------------------------------- #
async def _run_task(args: argparse.Namespace) -> None:
    """Выполняет одну задачу через SwarmWorker."""
    from swarm_scale.task import Task

    config = _load_config(args.config)
    from swarm_scale.worker import SwarmWorker

    worker = SwarmWorker(config)

    task = Task(
        task_id=f"cli-{os.urandom(4).hex()}",
        content=args.text,
        repository=args.repository or "cli/local",
        file_path=args.file_path or "unknown",
    )

    result = await worker.process_task(task)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False, default=str))
    else:
        print(f"\n{'='*60}")
        print(f"  Задача: {args.text[:60]}...")
        print(f"{'='*60}")
        print(f"  Статус: {'OK' if result.error is None else 'ERROR'}")
        if result.cached:
            print(f"  ⚡ Взято из кэша!")
        if result.error:
            print(f"  ❌ Ошибка: {result.error}")
        else:
            print(f"\n  📋 План архитектора:\n{result.plan}\n")
            print(f"  💻 Код:\n{result.code}\n")
            print(f"  🔍 Ревью: {'✅ APPROVED' if result.approved else '❌ REJECTED'}")
        print(f"  ⏱  {result.duration_sec:.2f} сек")
        print(f"{'='*60}")

    # Обновляем статистику
    stats = worker.stats
    print(f"\nСтатистика воркера: processed={stats['processed']},"
          f" cached={stats['cached']}, errors={stats['errors']}")


# --------------------------------------------------------------------------- #
# Режим: батч задач
# --------------------------------------------------------------------------- #
async def _run_batch(args: argparse.Namespace) -> None:
    """Выполняет батч задач из JSON-файла."""
    from swarm_scale.task import Task

    config = _load_config(args.config)
    from swarm_scale.worker import SwarmWorker

    worker = SwarmWorker(config)

    # Загружаем задачи из JSON
    batch_path = Path(args.file)
    if not batch_path.exists():
        print(f"❌ Файл не найден: {batch_path}")
        sys.exit(1)

    with open(batch_path, "r", encoding="utf-8") as f:
        raw_tasks = json.load(f)

    tasks = [
        Task(
            task_id=t.get("task_id", f"batch-{i}"),
            content=t["content"],
            repository=t.get("repository", "cli/local"),
            file_path=t.get("file_path", "unknown"),
        )
        for i, t in enumerate(raw_tasks)
    ]

    print(f"Загружено задач: {len(tasks)}")
    results = await worker.process_batch(tasks)

    # Сохраняем результаты
    out_path = batch_path.with_name(batch_path.stem + "_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(
            [r.to_dict() for r in results],
            f,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

    # Сводка
    success = sum(1 for r in results if r.error is None and not r.cached)
    cached = sum(1 for r in results if r.cached)
    failed = sum(1 for r in results if r.error is not None)

    print(f"\n{'='*60}")
    print(f"  Батч завершён")
    print(f"{'='*60}")
    print(f"  ✅ Успешно:  {success}")
    print(f"  ⚡ Из кэша:  {cached}")
    print(f"  ❌ Ошибок:   {failed}")
    print(f"  Всего:      {len(results)}")
    print(f"  Результаты: {out_path}")
    print(f"{'='*60}")

    stats = worker.stats
    print(f"\nСтатистика воркера: processed={stats['processed']},"
          f" cached={stats['cached']}, errors={stats['errors']}")


# --------------------------------------------------------------------------- #
# Режим: daemon-воркер
# --------------------------------------------------------------------------- #
async def _run_worker(args: argparse.Namespace) -> None:
    """Запускает воркер в режиме daemon с очередью."""
    config = _load_config(args.config)

    # Опционально запускаем metrics-сервер
    if config.enable_metrics:
        try:
            from swarm_scale.metrics import start_metrics_server
            start_metrics_server(config.metrics_port)
            print(f"📊 Prometheus metrics: http://0.0.0.0:{config.metrics_port}")
        except Exception as e:
            print(f"⚠️  Metrics server error: {e}")

    # Создаём очередь
    queue_type = args.queue or ("kafka" if config.kafka_bootstrap_servers else "memory")
    if queue_type == "kafka":
        if not config.kafka_bootstrap_servers:
            print("❌ Kafka queue требует SCALE_KAFKA_SERVERS")
            sys.exit(1)
        from swarm_scale.queue import KafkaQueue
        queue = KafkaQueue(
            bootstrap_servers=config.kafka_bootstrap_servers,
            input_topic=config.kafka_input_topic,
            output_topic=config.kafka_output_topic,
        )
    else:
        from swarm_scale.queue import InMemoryQueue
        queue = InMemoryQueue()

    from swarm_scale.worker import SwarmWorker
    worker = SwarmWorker(config)

    # Обработка сигналов для graceful shutdown
    shutdown_event = asyncio.Event()

    def _signal_handler():
        print("\n⏹  Получен сигнал завершения. Завершаю работу...")
        shutdown_event.set()

    if sys.platform != "win32":
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, _signal_handler)
            except NotImplementedError:
                pass

    print(f"🚀 Воркер запущен (очередь: {queue_type}, "
          f"макс. воркеров: {config.max_workers})")
    print("  Ожидание задач... (Ctrl+C для выхода)\n")

    try:
        while not shutdown_event.is_set():
            task = await queue.pop()
            if task is None:
                await asyncio.sleep(0.5)
                continue

            print(f"📥 Получена задача: {task.task_id} | {task.content[:50]}...")
            result = await worker.process_task(task)
            await queue.acknowledge(task.task_id)

            status = "✅" if result.error is None else "❌"
            src = " ⚡(кэш)" if result.cached else ""
            print(f"  {status} {task.task_id}{src} | ⏱ {result.duration_sec:.2f}с")

            stats = worker.stats
            print(f"  📊 processed={stats['processed']}, "
                  f"cached={stats['cached']}, errors={stats['errors']}")

    except asyncio.CancelledError:
        pass

    print(f"\nВоркер остановлен.")
    stats = worker.stats
    print(f"Итого: processed={stats['processed']}, "
          f"cached={stats['cached']}, errors={stats['errors']}")


# --------------------------------------------------------------------------- #
# Парсер аргументов
# --------------------------------------------------------------------------- #
def _build_parser() -> argparse.ArgumentParser:
    """Создаёт парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="swarm-scale",
        description="Масштабируемая enterprise-система роя AI-агентов",
    )
    parser.add_argument(
        "--config", "-c",
        help="Путь к .env файлу конфигурации",
        default=None,
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Подробный вывод (DEBUG-логирование)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Вывод в JSON-формате (только для режима task)",
    )

    subparsers = parser.add_subparsers(dest="mode", help="Режим работы")

    # task
    task_parser = subparsers.add_parser("task", help="Выполнить одну задачу")
    task_parser.add_argument("text", type=str, help="Текст технического задания")
    task_parser.add_argument("--repo", dest="repository", help="Репозиторий (org/repo)")
    task_parser.add_argument("--file", dest="file_path", help="Путь к файлу")

    # batch
    batch_parser = subparsers.add_parser("batch", help="Выполнить батч задач из JSON")
    batch_parser.add_argument("file", type=str, help="Путь к JSON-файлу с задачами")

    # worker
    worker_parser = subparsers.add_parser("worker", help="Запустить воркер в режиме daemon")
    worker_parser.add_argument(
        "--queue", choices=["memory", "kafka"], default=None,
        help="Тип очереди (по умолчанию: memory или kafka из конфига)",
    )

    return parser


# --------------------------------------------------------------------------- #
# Точка входа
# --------------------------------------------------------------------------- #
def main() -> None:
    """Главная точка входа CLI."""
    parser = _build_parser()
    args = parser.parse_args()

    _setup_logging(args.verbose)

    if args.mode == "task":
        asyncio.run(_run_task(args))
    elif args.mode == "batch":
        asyncio.run(_run_batch(args))
    elif args.mode == "worker":
        asyncio.run(_run_worker(args))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
