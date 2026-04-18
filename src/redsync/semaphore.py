from __future__ import annotations

import asyncio
import time
from enum import Enum
from pathlib import Path

from redis.asyncio import Redis
from redis.exceptions import WatchError

from .exceptions import (
    RedisSemaphoreCountError,
    RedisSemaphoreCountMismatchError,
    RedisSemaphoreNotAcquiredError,
    RedisSemaphoreTimeoutError,
)


class SemaphoreInitStrategy(str, Enum):
    LUA = "lua"
    OPTIMISTIC_LOCKING = "optimistic_locking"


LUA_SCRIPTS_DIR = Path(__file__).resolve().parent / "lua_scripts"


class RedisSemaphore:
    SENTINEL_VALUE = b"42"

    def __init__(
        self,
        redis_client: Redis,
        name: str,
        *,
        count: int,
        semaphore_init_strategy: SemaphoreInitStrategy = SemaphoreInitStrategy.LUA,
        key_prefix: str = "redis_semaphore",
    ) -> None:
        if not (1 <= count <= 4096):
            raise RedisSemaphoreCountError(count)

        self._redis = redis_client
        self.name = name
        self._count = count
        self._semaphore_init_strategy = semaphore_init_strategy
        self._prefix = key_prefix.rstrip(":")

        self._list_key = f"{self._prefix}:{name}:list"
        self._meta_key = f"{self._prefix}:{name}:meta"
        self._init_key = f"{self._prefix}:{name}:init"

        self._acquired = False

    @classmethod
    async def create(
        cls,
        redis_client: Redis,
        name: str,
        *,
        count: int = 1,
        semaphore_init_strategy: SemaphoreInitStrategy = SemaphoreInitStrategy.LUA,
        key_prefix: str = "redis_semaphore",
    ) -> RedisSemaphore:
        """
        Create or ensure the existence of a distributed semaphore with a specific count.

        This method is idempotent and safe to call concurrently from multiple identical
        workers. If the semaphore does not exist, it will be initialized atomically.
        If it already exists, it will validate that the existing count matches the
        requested `count`. If they do not match, it raises `RedisSemaphoreCountMismatchError`.

        Semantic Intent:
        Use this method for your Control Plane—when your code acts as the source of truth
        for the concurrency limit (count) and needs to ensure the semaphore is initialized.
        If you have pure consumer workers that shouldn't dictate the count, use `attach()` instead.
        """
        instance = cls(
            redis_client,
            name,
            count=count,
            semaphore_init_strategy=semaphore_init_strategy,
            key_prefix=key_prefix,
        )
        if instance._semaphore_init_strategy == SemaphoreInitStrategy.LUA:
            await instance._init_lua()
        else:
            await instance._init_optimistic_locking()

        return instance

    @classmethod
    async def attach(
        cls,
        redis_client: Redis,
        name: str,
        *,
        timeout: float | None = 60.0,
        key_prefix: str = "redis_semaphore",
    ) -> RedisSemaphore:
        """
        Attach to an already existing distributed semaphore without specifying a count.

        This method acts as a pure consumer. It does not attempt to initialize the
        semaphore. Instead, it waits (polls metadata) for the semaphore to be created
        by another process.

        Semantic Intent:
        Using `attach()` cleanly separates your Control Plane (which dictates limits
        and calls `create()`) from your Data Plane (workers that consume resources).
        It simplifies worker code because workers do not need to hardcode or know
        the count beforehand.

        Use this method in worker processes when the semaphore's lifecycle and count
        are managed elsewhere (e.g., by a central manager script), or when you simply
        want to connect to a resource without asserting its concurrency limit.

        Raises:
            RedisSemaphoreTimeoutError: If the semaphore is not created within `timeout` seconds.
        """
        prefix = key_prefix.rstrip(":")
        meta_key = f"{prefix}:{name}:meta"

        start_time = time.monotonic()
        while True:
            meta_count = await redis_client.hget(meta_key, "count")  # type: ignore
            if meta_count is not None:
                count = int(meta_count)
                break

            if timeout is not None and time.monotonic() - start_time >= timeout:
                raise RedisSemaphoreTimeoutError

            await asyncio.sleep(0.05)

        return cls(
            redis_client,
            name,
            count=count,
            key_prefix=key_prefix,
        )

    async def acquire(self, timeout: float | None = None) -> None:
        timeout = 0 if timeout is None else max(0, timeout)
        result = await self._redis.blpop(self._list_key, timeout=timeout)  # type: ignore
        if result is None:
            raise RedisSemaphoreTimeoutError

        self._acquired = True

    async def release(self) -> None:
        if not self._acquired:
            raise RedisSemaphoreNotAcquiredError

        await self._redis.rpush(self._list_key, self.SENTINEL_VALUE)  # type: ignore
        self._acquired = False

    async def __aenter__(self) -> RedisSemaphore:
        await self.acquire()
        return self

    async def __aexit__(
        self, exc_type: object, exc_val: object, exc_tb: object
    ) -> None:
        await self.release()

    async def get_count(self) -> int:
        return self._count

    async def _init_lua(self) -> None:
        script_obj = self._redis.register_script(
            (LUA_SCRIPTS_DIR / "init_semaphore.lua").read_text()
        )
        actual_count = await script_obj(
            keys=[self._list_key, self._meta_key],
            args=[str(self._count), self.SENTINEL_VALUE],
        )  # type: ignore[return-value]

        if int(actual_count) != self._count:
            raise RedisSemaphoreCountMismatchError(self._count, int(actual_count))

    async def _init_optimistic_locking(self) -> None:
        async with self._redis.pipeline(transaction=True) as pipe:
            while True:
                try:
                    await pipe.watch(self._meta_key)
                    meta_count = await pipe.hget(self._meta_key, "count")  # type: ignore

                    if meta_count is not None:
                        if int(meta_count) != self._count:
                            raise RedisSemaphoreCountMismatchError(
                                self._count, int(meta_count)
                            )
                        return

                    pipe.multi()
                    pipe.hset(self._meta_key, "count", self._count)  # type: ignore
                    pipe.rpush(self._list_key, *([self.SENTINEL_VALUE] * self._count))  # type: ignore
                    await pipe.execute()
                    return
                except WatchError:
                    continue
