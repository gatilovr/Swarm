"""Пример использования Swarm — создание функции быстрой сортировки.

Запуск:
    python examples/quicksort.py
"""

from swarm import SwarmRunner


def main() -> None:
    """Запускает рой AI-агентов для задачи создания quicksort."""
    print("=" * 60)
    print("  🤖 Пример: Рой AI-агентов")
    print("  Задача: Функция быстрой сортировки (quicksort)")
    print("=" * 60)

    # Создание runner'а с конфигом из .env
    runner = SwarmRunner()

    # Задача для роя
    task = (
        "Напиши функцию на Python для быстрой сортировки (quicksort) "
        "с подробными комментариями на русском языке. "
        "Функция должна принимать список чисел и возвращать отсортированный список. "
        "Добавь также пример использования."
    )

    print(f"\n📝 Задача: {task}\n")
    print("Запуск роя агентов...\n")

    # Запуск с пошаговым выводом
    for step in runner.stream(task):
        node = step.get("node", "")
        emoji = step.get("emoji", "🤖")
        label = step.get("label", "")
        if label:
            print(f"  {emoji} {label} завершил работу")

    # Получение финального результата после stream
    final = runner._last_result

    print("\n📋 План архитектора:")
    print("-" * 40)
    print(final.get("plan", "Нет плана"))

    print("\n💻 Код:")
    print("-" * 40)
    print(final.get("code", "Нет кода"))

    print("\n🔍 Результат ревью:")
    print("-" * 40)
    print(final.get("review_result", "Нет ревью"))

    print("\n" + "=" * 60)
    print("  ✅ Готово!")
    print("=" * 60)


if __name__ == "__main__":
    main()
