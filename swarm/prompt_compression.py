"""Prompt compression using LLMLingua (Microsoft).

Позволяет сжимать промпты перед отправкой в LLM, сокращая
потребление токенов на 40-60% для больших контекстов без потери качества.

Использует LLMLingua от Microsoft Research (llmlingua>=2.0.0).
Graceful fallback: если LLMLingua не установлена, работает без сжатия.
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SwarmPromptCompressor:
    """Сжимает промпты для экономии токенов.

    Использует LLMLingua от Microsoft Research.
    Применяется только для контекстов > min_tokens токенов.
    Graceful fallback: если LLMLingua не установлена, работает без сжатия.

    Пример использования:
        compressor = SwarmPromptCompressor(rate=0.5, min_tokens=4096)
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write an essay..."},
        ]
        compressed = compressor.compress_messages(messages)
    """

    def __init__(
        self,
        rate: float = 0.5,
        min_tokens: int = 4096,
        force_compress: bool = False,
        model_name: str = "microsoft/llmlingua-2-xlm-roberta-large-meetingbank",
    ) -> None:
        """Инициализирует компрессор.

        Args:
            rate: коэффициент сжатия (0.0-1.0), где 0.5 = сжать в 2 раза.
            min_tokens: минимальное количество токенов для применения сжатия.
            force_compress: принудительное сжатие даже для маленьких контекстов.
            model_name: имя модели LLMLingua для компрессии.
        """
        self.rate = rate
        self.min_tokens = min_tokens
        self.force_compress = force_compress
        self._model_name = model_name
        self._compressor: Optional[object] = None
        self._available: Optional[bool] = None

    # ------------------------------------------------------------------
    # Публичные свойства
    # ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        """Проверяет доступность LLMLingua.

        Returns:
            True, если библиотека llmlingua установлена и импортируема.
        """
        if self._available is not None:
            return self._available
        try:
            # noqa — импорт для проверки доступности, не для использования
            from llmlingua import PromptCompressor  # type: ignore[import-untyped]  # noqa: F401
            self._available = True
            logger.debug("LLMLingua доступна")
        except ImportError:
            self._available = False
            logger.info("LLMLingua не установлена — сжатие отключено")
        return self._available

    # ------------------------------------------------------------------
    # Публичные методы
    # ------------------------------------------------------------------

    def estimate_tokens(self, messages: list[dict[str, str]]) -> int:
        """Грубая оценка количества токенов (4 символа ≈ 1 токен).

        Быстрая эвристика без вызова токенизатора.
        Для точного подсчёта используйте count_tokens() провайдера.

        Args:
            messages: список сообщений [{"role": "...", "content": "..."}]

        Returns:
            int: estimated количество токенов
        """
        total_chars = sum(len(m.get("content", "")) for m in messages)
        return total_chars // 4

    def compress_messages(
        self,
        messages: list[dict[str, str]],
        rate: Optional[float] = None,
    ) -> list[dict[str, str]]:
        """Сжимает сообщения.

        Правила сжатия:
        1. System messages (role="system") НЕ сжимаются — это инструкции агента.
        2. Non-system сообщения сжимаются через LLMLingua.
        3. Если контекст меньше min_tokens — возвращается без изменений.
        4. Если LLMLingua недоступна — возвращается без изменений (graceful fallback).

        Args:
            messages: список сообщений [{"role": "...", "content": "..."}]
            rate: коэффициент сжатия (0.0-1.0). Если None, используется self.rate.

        Returns:
            Сжатые сообщения (или оригинальные, если сжатие не применимо).
        """
        # Проверка: доступна ли LLMLingua
        if not self.available and not self.force_compress:
            logger.debug("LLMLingua недоступна — пропускаем сжатие")
            return messages

        # Проверка: достаточно ли большой контекст
        estimated = self.estimate_tokens(messages)
        if estimated < self.min_tokens and not self.force_compress:
            logger.debug(
                "Контекст слишком мал для сжатия (%d < %d токенов)",
                estimated,
                self.min_tokens,
            )
            return messages

        # Пытаемся получить компрессор
        compressor = self._get_compressor()
        if compressor is None:
            logger.debug("Компрессор не инициализирован — fallback")
            return messages

        target_rate = rate or self.rate

        try:
            # Разделяем system сообщения и остальные
            system_msgs = [m for m in messages if m.get("role") == "system"]
            other_msgs = [m for m in messages if m.get("role") != "system"]

            # Если нет non-system сообщений — нечего сжимать
            if not other_msgs:
                return messages

            # Склеиваем non-system сообщения в один текст для компрессии
            other_text = "\n".join(
                f"{m['role']}: {m['content']}" for m in other_msgs
            )

            # Вызываем LLMLingua
            compressed = compressor.compress(
                other_text,
                rate=target_rate,
                force_tokens=[],
                iterations=5,
            )

            compressed_text = compressed.get("compressed_prompt", other_text)

            # Собираем результат: system сообщения + одно сжатое user сообщение
            result: list[dict[str, str]] = list(system_msgs)
            result.append({
                "role": "user",
                "content": compressed_text,
            })

            original_tokens = self.estimate_tokens(other_msgs)
            compressed_tokens = len(compressed_text) // 4
            logger.debug(
                "Сжатие: %d → %d токенов (rate=%.2f)",
                original_tokens,
                compressed_tokens,
                target_rate,
            )

            return result

        except Exception as exc:
            logger.warning("Ошибка при сжатии промпта: %s — fallback", exc)
            return messages

    # ------------------------------------------------------------------
    # Внутренние методы
    # ------------------------------------------------------------------

    def _get_compressor(self) -> Optional[object]:
        """Lazy-init компрессора LLMLingua.

        Returns:
            PromptCompressor или None, если библиотека не установлена.
        """
        if self._compressor is not None:
            return self._compressor

        if not self.available:
            return None

        try:
            from llmlingua import PromptCompressor  # type: ignore[import-untyped]

            self._compressor = PromptCompressor(model_name=self._model_name)
            logger.debug("Компрессор LLMLingua инициализирован (model=%s)", self._model_name)
        except Exception as exc:
            logger.warning("Не удалось инициализировать LLMLingua: %s", exc)
            self._available = False
            self._compressor = None

        return self._compressor
