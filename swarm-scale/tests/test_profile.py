"""Тесты для модуля профилей проектов."""

import pytest
from swarm_scale.profile import ProjectProfile, ProfileManager


class TestProjectProfile:
    """Тесты dataclass ProjectProfile."""

    def test_create_minimal(self):
        """Создание профиля с минимальными полями."""
        profile = ProjectProfile(
            profile_id="test-1",
            repository="org/repo",
        )
        assert profile.profile_id == "test-1"
        assert profile.repository == "org/repo"
        assert profile.language == "python"
        assert profile.framework is None
        assert profile.test_framework == "pytest"
        assert profile.linting_rules == []
        assert profile.style_guide is None
        assert profile.additional_context == ""

    def test_create_full(self):
        """Создание профиля со всеми полями."""
        profile = ProjectProfile(
            profile_id="full-1",
            repository="org/backend",
            language="rust",
            framework="axum",
            test_framework="cargo-test",
            linting_rules=["clippy"],
            style_guide="rustfmt",
            additional_context="Legacy codebase, careful with refactoring",
        )
        assert profile.language == "rust"
        assert profile.framework == "axum"
        assert profile.style_guide == "rustfmt"
        assert "clippy" in profile.linting_rules

    def test_default_values(self):
        """Проверка значений по умолчанию."""
        profile = ProjectProfile(profile_id="d", repository="r")
        assert profile.test_framework == "pytest"
        assert profile.linting_rules == []
        assert isinstance(profile.linting_rules, list)
        assert len(profile.linting_rules) == 0

    def test_linting_rules_immutable_default(self):
        """linting_rules не должен разделять один список между инстансами."""
        p1 = ProjectProfile(profile_id="1", repository="r1")
        p2 = ProjectProfile(profile_id="2", repository="r2")

        p1.linting_rules.append("ruff")
        assert len(p1.linting_rules) == 1
        assert len(p2.linting_rules) == 0  # не должен измениться


class TestProfileManager:
    """Тесты ProfileManager."""

    @pytest.fixture
    def manager(self):
        return ProfileManager()

    @pytest.fixture
    def sample_profile(self):
        return ProjectProfile(
            profile_id="python-fastapi",
            repository="org/my-api",
            language="python",
            framework="fastapi",
        )

    def test_register(self, manager, sample_profile):
        """Регистрация профиля."""
        manager.register(sample_profile)
        assert manager.count == 1

    def test_get_by_id(self, manager, sample_profile):
        """Получение профиля по ID."""
        manager.register(sample_profile)
        result = manager.get("python-fastapi")
        assert result is not None
        assert result.repository == "org/my-api"
        assert result.framework == "fastapi"

    def test_get_nonexistent(self, manager):
        """None для несуществующего ID."""
        result = manager.get("nonexistent")
        assert result is None

    def test_get_by_repository(self, manager, sample_profile):
        """Поиск по репозиторию."""
        manager.register(sample_profile)
        result = manager.get_by_repository("org/my-api")
        assert result is not None
        assert result.profile_id == "python-fastapi"

    def test_get_by_repository_nonexistent(self, manager):
        """None для несуществующего репозитория."""
        result = manager.get_by_repository("org/unknown")
        assert result is None

    def test_remove(self, manager, sample_profile):
        """Удаление профиля."""
        manager.register(sample_profile)
        assert manager.count == 1

        removed = manager.remove("python-fastapi")
        assert removed is True
        assert manager.count == 0
        assert manager.get("python-fastapi") is None

    def test_remove_nonexistent(self, manager):
        """False при удалении отсутствующего профиля."""
        result = manager.remove("nonexistent")
        assert result is False

    def test_count(self, manager):
        """Количество профилей."""
        assert manager.count == 0

        manager.register(ProjectProfile(profile_id="1", repository="r1"))
        assert manager.count == 1

        manager.register(ProjectProfile(profile_id="2", repository="r2"))
        assert manager.count == 2

        manager.register(ProjectProfile(profile_id="3", repository="r3"))
        assert manager.count == 3

    def test_register_duplicate(self, manager):
        """Перезапись при дубликате ID."""
        p1 = ProjectProfile(profile_id="dup", repository="org/repo1")
        p2 = ProjectProfile(profile_id="dup", repository="org/repo2")

        manager.register(p1)
        manager.register(p2)  # перезаписывает

        result = manager.get("dup")
        assert result.repository == "org/repo2"  # последний

    def test_multiple_profiles_search(self, manager):
        """Поиск среди нескольких профилей."""
        profiles = [
            ProjectProfile(profile_id="a", repository="org/a"),
            ProjectProfile(profile_id="b", repository="org/b"),
            ProjectProfile(profile_id="c", repository="org/c"),
        ]
        for p in profiles:
            manager.register(p)

        assert manager.get_by_repository("org/b").profile_id == "b"
        assert manager.get_by_repository("org/none") is None
