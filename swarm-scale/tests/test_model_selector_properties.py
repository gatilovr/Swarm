"""Property-based тесты для адаптивного выбора модели.

Инварианты:
- ModelSelector.select() всегда возвращает ModelConfig (не None)
- ModelConfig всегда содержит валидные имена моделей
- Классификация стабильна: повторный вызов с теми же данными → тот же результат
- force_complexity переопределяет авто-классификацию
- select() не падает для любых входных данных
"""
import pytest
from hypothesis import given, strategies as st
from swarm_scale.model_selector import ModelSelector, ModelConfig


# Стратегии
task_strategy = st.text(min_size=0, max_size=500)
force_strategy = st.one_of(
    st.none(),
    st.just("auto"),
    st.sampled_from(["low", "medium", "high", "critical"]),
)
valid_models = ["deepseek-chat", "deepseek-reasoner"]


class TestModelSelectorProperties:
    """Property-based тесты ModelSelector."""

    def test_selector_always_returns_model_config(self):
        """ModelSelector.select() всегда возвращает ModelConfig с непустым model_name."""
        selector = ModelSelector()
        result = selector.select("Напиши калькулятор на Python")
        assert isinstance(result, ModelConfig)
        assert result.architect in valid_models
        assert result.coder in valid_models
        assert result.provider == "litellm"

    @given(
        task_content=task_strategy,
        force=force_strategy,
    )
    def test_selector_never_crashes(self, task_content, force):
        """ModelSelector.select() не падает для любых входных данных."""
        selector = ModelSelector()
        result = selector.select(task_content, force_complexity=force)
        assert isinstance(result, ModelConfig)
        assert isinstance(result.architect, str)
        assert isinstance(result.coder, str)
        assert len(result.architect) > 0
        assert len(result.coder) > 0

    @given(
        task_content=st.text(min_size=10, max_size=500),
    )
    def test_selector_classification_stable(self, task_content):
        """Классификация стабильна: повторный вызов даёт тот же результат."""
        selector = ModelSelector()
        result1 = selector.select(task_content)
        result2 = selector.select(task_content)
        assert result1.architect == result2.architect
        assert result1.coder == result2.coder
        assert result1.reviewer == result2.reviewer
        assert result1.skip_review == result2.skip_review

    @given(
        task_content=st.text(min_size=10, max_size=500, alphabet="abcdefghijklmnopqrstuvwxyz "),
    )
    def test_selector_force_overrides(self, task_content):
        """force_complexity переопределяет авто-классификацию."""
        selector = ModelSelector()

        result_auto = selector.select(task_content, force_complexity="auto")
        result_low = selector.select(task_content, force_complexity="low")

        assert isinstance(result_low, ModelConfig)
        assert result_low.architect is not None

        # force="low" всегда даёт skip_review=True
        assert result_low.skip_review is True
        assert result_low.reviewer is None

    @given(
        task_content=st.text(min_size=10, max_size=500, alphabet="abcdefghijklmnopqrstuvwxyz "),
    )
    def test_selector_force_critical(self, task_content):
        """force_complexity='critical' всегда даёт deepseek-reasoner."""
        selector = ModelSelector()
        result = selector.select(task_content, force_complexity="critical")
        assert result.architect == "deepseek-reasoner"

    @given(
        task_content=st.text(min_size=10, max_size=500, alphabet="abcdefghijklmnopqrstuvwxyz "),
    )
    def test_selector_temperature_always_set(self, task_content):
        """ModelConfig.temperature всегда определён."""
        selector = ModelSelector()
        result = selector.select(task_content)
        assert isinstance(result.temperature, float)
        assert 0.0 <= result.temperature <= 1.0

    @given(
        task_content=st.text(min_size=10, max_size=500, alphabet="abcdefghijklmnopqrstuvwxyz "),
    )
    def test_selector_display_name_not_empty(self, task_content):
        """display_name не пустой после создания."""
        selector = ModelSelector()
        result = selector.select(task_content)
        assert len(result.display_name) > 0
        assert result.display_name == result.architect

    def test_selector_stats_always_dict(self):
        """stats всегда возвращает dict с 4 ключами."""
        selector = ModelSelector()
        stats = selector.stats
        assert isinstance(stats, dict)
        assert set(stats.keys()) == {"critical", "high", "medium", "low"}
        for v in stats.values():
            assert isinstance(v, int)
            assert v >= 0

    @given(
        task_contents=st.lists(
            st.text(min_size=5, max_size=100, alphabet="abcdefghijklmnopqrstuvwxyz "),
            min_size=1, max_size=20,
        ),
    )
    def test_selector_stats_accumulate(self, task_contents):
        """Статистика накапливается: каждый вызов увеличивает счётчик."""
        selector = ModelSelector()
        for tc in task_contents:
            selector.select(tc)
        stats = selector.stats
        total = sum(stats.values())
        assert total == len(task_contents)

    @given(
        task_content=task_strategy,
    )
    def test_selector_reviewer_consistency(self, task_content):
        """Если skip_review=True, то reviewer=None, и наоборот."""
        selector = ModelSelector()
        result = selector.select(task_content)
        if result.skip_review:
            assert result.reviewer is None
        else:
            assert result.reviewer is not None
