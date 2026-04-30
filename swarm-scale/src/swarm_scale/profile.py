"""Профиль проекта для настройки параметров роя."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProjectProfile:
    """Профиль проекта с настройками для роя.

    Поля:
        profile_id: уникальный идентификатор профиля
        repository: репозиторий
        language: основной язык программирования
        framework: используемый фреймворк
        test_framework: фреймворк для тестов
        linting_rules: правила линтинга
        style_guide: стайлгайд
        additional_context: дополнительный контекст
    """
    profile_id: str
    repository: str
    language: str = "python"
    framework: Optional[str] = None
    test_framework: str = "pytest"
    linting_rules: list[str] = field(default_factory=list)
    style_guide: Optional[str] = None
    additional_context: str = ""


class ProfileManager:
    """Менеджер профилей проектов.

    Позволяет создавать, сохранять, получать и перечислять
    профили проектов (``ProjectProfile``), содержащие настройки
    языка, фреймворка, правил линтинга и стайлгайда.
    """

    def __init__(self):
        """Инициализирует ProfileManager.

        Создаёт внутреннее хранилище профилей (``dict[str, ProjectProfile]``).
        """
        self._profiles: dict[str, ProjectProfile] = {}

    def register(self, profile: ProjectProfile) -> None:
        """Регистрирует профиль проекта.

        Args:
            profile: профиль проекта
        """
        self._profiles[profile.profile_id] = profile

    def get(self, profile_id: str) -> Optional[ProjectProfile]:
        """Получает профиль по ID.

        Args:
            profile_id: идентификатор профиля

        Returns:
            Optional[ProjectProfile]: профиль или None
        """
        return self._profiles.get(profile_id)

    def get_by_repository(self, repository: str) -> Optional[ProjectProfile]:
        """Ищет профиль по репозиторию.

        Args:
            repository: репозиторий

        Returns:
            Optional[ProjectProfile]: профиль или None
        """
        for profile in self._profiles.values():
            if profile.repository == repository:
                return profile
        return None

    def remove(self, profile_id: str) -> bool:
        """Удаляет профиль.

        Args:
            profile_id: идентификатор профиля

        Returns:
            bool: True если удалён
        """
        return self._profiles.pop(profile_id, None) is not None

    def get_profile(self, profile_id: str) -> Optional[ProjectProfile]:
        """Получает профиль проекта по идентификатору.

        Args:
            profile_id: уникальный идентификатор профиля.

        Returns:
            Optional[ProjectProfile]: профиль проекта или ``None``, если не найден.
        """
        return self._profiles.get(profile_id)

    def save_profile(self, profile: ProjectProfile) -> None:
        """Сохраняет (регистрирует) профиль проекта.

        Если профиль с таким ``profile_id`` уже существует,
        он будет перезаписан.

        Args:
            profile: профиль проекта для сохранения.
        """
        self._profiles[profile.profile_id] = profile

    def list_profiles(self) -> list[ProjectProfile]:
        """Возвращает список всех зарегистрированных профилей.

        Returns:
            list[ProjectProfile]: список профилей проектов.
        """
        return list(self._profiles.values())

    @property
    def count(self) -> int:
        """Количество зарегистрированных профилей."""
        return len(self._profiles)
