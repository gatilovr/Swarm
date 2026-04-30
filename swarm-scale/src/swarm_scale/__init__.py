"""Swarm Scale — масштабируемая enterprise-система роя AI-агентов."""

from .config import ScaleConfig
from .worker import SwarmWorker
from .task import Task, TaskResult, TaskPriority, TaskStatus
from .cache import CacheManager, DiskCache, RedisCache
from .rate_limiter import AdaptiveRateLimiter
from .model_selector import ModelSelector, ModelConfig
from .context import ContextBuilder, ProjectContext
from .profile import ProfileManager, ProjectProfile
from .queue import TaskQueue, InMemoryQueue, KafkaQueue

__version__ = "1.0.0"

__all__ = [
    "ScaleConfig",
    "SwarmWorker",
    "Task", "TaskResult", "TaskPriority", "TaskStatus",
    "CacheManager", "DiskCache", "RedisCache",
    "AdaptiveRateLimiter",
    "ModelSelector", "ModelConfig",
    "ContextBuilder", "ProjectContext",
    "ProfileManager", "ProjectProfile",
    "TaskQueue", "InMemoryQueue", "KafkaQueue",
]
