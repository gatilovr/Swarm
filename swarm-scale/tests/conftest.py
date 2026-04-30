"""Конфигурация pytest для тестов swarm-scale."""
import sys
import shutil
from pathlib import Path

from hypothesis import settings, HealthCheck

# Добавляем родительскую директорию swarm, чтобы from swarm.config находил пакет
SWARM_PARENT = Path(__file__).resolve().parent.parent.parent  # Swarm/
SWARM_DIR = SWARM_PARENT / "swarm"
if SWARM_DIR.exists():
    sys.path.insert(0, str(SWARM_PARENT))

# Очищаем кэш-директорию между запусками тестов
CACHE_DIR = Path(__file__).resolve().parent.parent / ".swarm_cache"
if CACHE_DIR.exists():
    shutil.rmtree(str(CACHE_DIR))

# Hypothesis profiles
settings.register_profile("ci", max_examples=50, suppress_health_check=[HealthCheck.too_slow])
settings.register_profile("dev", max_examples=10)
settings.load_profile("ci")
