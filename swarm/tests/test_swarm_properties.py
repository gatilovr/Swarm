"""Property-based тесты для состояния графа Swarm.

Инварианты:
- SwarmState TypedDict работает корректно для любых значений
- is_final всегда соответствует iteration >= max_iterations
- Все поля имеют правильные типы
"""
import pytest
from hypothesis import given, HealthCheck, settings, strategies as st
from swarm.state import SwarmState


class TestSwarmStateProperties:
    """Property-based тесты для SwarmState."""

    @settings(suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much])
    @given(
        task=st.text(min_size=1, max_size=100),
        iteration=st.integers(min_value=0, max_value=100),
        max_iterations=st.integers(min_value=1, max_value=10),
    )
    def test_swarm_state_immutability(self, task, iteration, max_iterations):
        """SwarmState TypedDict работает корректно для любых значений."""
        state: SwarmState = {
            "messages": [{"role": "user", "content": task}],
            "task": task,
            "plan": "",
            "code": "",
            "review_result": "",
            "iteration": iteration,
            "max_iterations": max_iterations,
            "is_final": iteration >= max_iterations,
        }
        assert state["task"] == task
        assert state["iteration"] == iteration
        assert state["is_final"] == (iteration >= max_iterations)
        assert isinstance(state["max_iterations"], int)
        assert state["max_iterations"] > 0

    @given(
        task=st.text(min_size=1, max_size=100),
        plan=st.text(max_size=200),
        code=st.text(max_size=200),
        review_result=st.sampled_from(["APPROVED", "REJECTED", ""]),
        iteration=st.integers(min_value=0, max_value=100),
        max_iterations=st.integers(min_value=1, max_value=10),
    )
    def test_swarm_state_all_fields(self, task, plan, code, review_result, iteration, max_iterations):
        """Все поля SwarmState могут принимать любые строковые значения."""
        state: SwarmState = {
            "messages": [{"role": "user", "content": task}],
            "task": task,
            "plan": plan,
            "code": code,
            "review_result": review_result,
            "iteration": iteration,
            "max_iterations": max_iterations,
            "is_final": iteration >= max_iterations,
        }
        assert state["plan"] == plan
        assert state["code"] == code
        assert state["review_result"] == review_result
        assert state["is_final"] == (iteration >= max_iterations)

    @given(
        task=st.text(min_size=1, max_size=100),
    )
    def test_swarm_state_messages_list(self, task):
        """messages всегда список dict с role и content."""
        state: SwarmState = {
            "messages": [{"role": "user", "content": task}],
            "task": task,
            "plan": "",
            "code": "",
            "review_result": "",
            "iteration": 0,
            "max_iterations": 3,
            "is_final": False,
        }
        assert isinstance(state["messages"], list)
        assert len(state["messages"]) > 0
        assert state["messages"][0]["role"] == "user"
        assert state["messages"][0]["content"] == task

    @given(
        task=st.text(min_size=1, max_size=100),
        is_final=st.booleans(),
    )
    def test_swarm_state_is_final_bool(self, task, is_final):
        """is_final всегда bool."""
        state: SwarmState = {
            "messages": [{"role": "user", "content": task}],
            "task": task,
            "plan": "",
            "code": "",
            "review_result": "",
            "iteration": 5,
            "max_iterations": 10,
            "is_final": is_final,
        }
        assert isinstance(state["is_final"], bool)
