from __future__ import annotations

from enum import Enum
from pathlib import Path

from redis.asyncio import Redis

from .exceptions import RedisSemaphoreCountError, RedisSemaphoreNotAcquiredError, RedisSemaphoreTimeoutError


class SemaphoreInitStrategy(str, Enum):
    LUA = "lua"
    SETNX = "setnx"


LUA_SCRIPTS_DIR = Path(__file__).resolve().parent / "lua_scripts"


class RedisSemaphore:
    SENTINEL_VALUE = b"42"

    def __init__(
        self,
        redis_client: Redis,
        name: str,
        *,
        count: int = 1,
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
            await instance._init_setnx()

        return instance

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

    async def __aexit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        await self.release()

    async def _init_lua(self) -> int:
        script_obj = self._redis.register_script((LUA_SCRIPTS_DIR / "init_semaphore.lua").read_text())
        return await script_obj(
            keys=[self._list_key],
            args=[str(self._count), self.SENTINEL_VALUE],
        )  # type: ignore[return-value]

    async def _init_setnx(self) -> None:
        if await self._redis.setnx(self._init_key, self.SENTINEL_VALUE):
            pipe = self._redis.pipeline()
            pipe.rpush(self._list_key, *([self.SENTINEL_VALUE] * self._count))
            pipe.delete(self._init_key)
            await pipe.execute()
