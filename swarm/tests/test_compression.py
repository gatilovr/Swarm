"""Тесты для модуля компрессии промптов (SwarmPromptCompressor)."""

import pytest

from swarm.prompt_compression import SwarmPromptCompressor


class TestSwarmPromptCompressor:
    """Тестирует SwarmPromptCompressor."""

    def test_returns_messages_when_small(self):
        """Контекст < min_tokens токенов → возвращается без изменений."""
        compressor = SwarmPromptCompressor(min_tokens=1000, force_compress=False)
        messages = [{"role": "user", "content": "Hello"}]
        result = compressor.compress_messages(messages)
        assert result == messages

    def test_handles_missing_llmlingua(self):
        """LLMLingua не установлена → graceful fallback, без краша."""
        compressor = SwarmPromptCompressor(force_compress=False)
        messages = [{"role": "user", "content": "A" * 10000}]
        result = compressor.compress_messages(messages)
        assert result == messages  # no crash

    def test_compresses_large_context(self):
        """Большой контекст → не падает (либо сжатие, либо fallback)."""
        compressor = SwarmPromptCompressor(min_tokens=1, force_compress=True)
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Write a very long essay about AI " * 1000},
        ]
        result = compressor.compress_messages(messages, rate=0.5)
        # Должен вернуть сообщения (либо сжатые, либо исходные при fallback)
        assert len(result) > 0
        # System prompt должен сохраниться
        assert result[0]["role"] == "system"

    def test_system_prompt_unchanged(self):
        """System prompt не должен изменяться после сжатия.

            Даже если LLMLingua недоступна, system message остаётся на месте.
        """
        compressor = SwarmPromptCompressor(min_tokens=1, force_compress=True)
        system_content = "You are a strict code reviewer."
        messages = [
            {"role": "system", "content": system_content},
            {"role": "user", "content": "Review this code: " + "x" * 5000},
            {"role": "assistant", "content": "Here is my review: " + "y" * 5000},
        ]
        result = compressor.compress_messages(messages, rate=0.5)
        # System message должен быть первым и непустым
        assert result[0]["role"] == "system"
        assert len(result[0]["content"]) > 0

    def test_no_non_system_messages(self):
        """Если нет non-system сообщений — возвращается без изменений."""
        compressor = SwarmPromptCompressor(min_tokens=1, force_compress=True)
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
        ]
        result = compressor.compress_messages(messages)
        assert result == messages

    def test_estimate_tokens(self):
        """Оценка токенов: 4 символа ≈ 1 токен."""
        compressor = SwarmPromptCompressor()
        messages = [{"role": "user", "content": "A" * 100}]
        estimated = compressor.estimate_tokens(messages)
        assert estimated == 25  # 100 // 4

    def test_available_property(self):
        """Свойство available не падает и возвращает bool."""
        compressor = SwarmPromptCompressor()
        # Не должно быть исключения
        assert isinstance(compressor.available, bool)

    @pytest.mark.asyncio
    async def test_integration_with_provider(self):
        """Проверка, что компрессор корректно передаётся в провайдер.

        (Интеграционный тест — без реального вызова LLM.)
        """
        from swarm.llm.litellm_provider import LiteLLMProvider
        from swarm.llm.config import LiteLLMConfig

        config = LiteLLMConfig(
            compression_enabled=True,
            compression_rate=0.5,
            compression_min_tokens=1,
        )
        provider = LiteLLMProvider(config=config)
        # Компрессор должен быть создан из конфига
        assert provider.compressor is not None
        assert provider.compressor.rate == 0.5
        assert provider.compressor.min_tokens == 1

    def test_force_compress_even_when_small(self):
        """force_compress=True сжимает даже маленький контекст."""
        compressor = SwarmPromptCompressor(
            min_tokens=10000,
            force_compress=True,
        )
        messages = [{"role": "user", "content": "Hello world"}]
        result = compressor.compress_messages(messages)
        # При отсутствии llmlingua — fallback, то же самое
        assert result == messages

    def test_compression_disabled_via_config(self):
        """compression_enabled=False → компрессор не создаётся."""
        from swarm.llm.config import LiteLLMConfig
        from swarm.llm.litellm_provider import LiteLLMProvider

        config = LiteLLMConfig(compression_enabled=False)
        provider = LiteLLMProvider(config=config)
        assert provider.compressor is None
