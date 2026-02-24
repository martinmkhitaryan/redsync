"""
Redis-based distributed synchronization primitives for Python.

Provides distributed semaphores and locking built on Redis for asyncio applications.
"""

from .exceptions import (
    RedisSemaphoreCountError,
    RedisSemaphoreNotAcquiredError,
    RedisSemaphoreTimeoutError,
)
from .semaphore import RedisSemaphore, SemaphoreInitStrategy

__version__ = "1.0.0"
__author__ = "Martin Mkhitaryan"
__email__ = "mkhitaryan.martin@2000gmail.com"

__all__ = [
    "RedisSemaphore",
    "SemaphoreInitStrategy",
    "RedisSemaphoreCountError",
    "RedisSemaphoreNotAcquiredError",
    "RedisSemaphoreTimeoutError",
]
