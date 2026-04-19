"""
Redis-based distributed synchronization primitives for Python.

Provides distributed semaphores and locking built on Redis for asyncio applications.
"""

from .event import RedisEvent
from .exceptions import (
    RedisEventError,
    RedisEventTimeoutError,
    RedisSemaphoreCountError,
    RedisSemaphoreCountMismatchError,
    RedisSemaphoreNotAcquiredError,
    RedisSemaphoreTimeoutError,
)
from .semaphore import RedisSemaphore, SemaphoreInitStrategy

__version__ = "2.0.0"
__author__ = "Martin Mkhitaryan"
__email__ = "mkhitaryan.martin@2000gmail.com"

__all__ = [
    "RedisSemaphore",
    "RedisEvent",
    "SemaphoreInitStrategy",
    "RedisSemaphoreCountError",
    "RedisSemaphoreCountMismatchError",
    "RedisSemaphoreNotAcquiredError",
    "RedisSemaphoreTimeoutError",
    "RedisEventError",
    "RedisEventTimeoutError",
]
