from __future__ import annotations

from redis.asyncio import Redis

from .exceptions import RedisEventTimeoutError


class RedisEvent:
    def __init__(
        self,
        redis_client: Redis,
        name: str,
        *,
        key_prefix: str = "redsync:event",
    ) -> None:
        self._redis = redis_client
        self.name = name
        self._key = f"{key_prefix.rstrip(':')}:{name}"

    async def set(self) -> None:
        await self._redis.lpush(self._key, 1)  # type: ignore

    async def wait(self, timeout: float | None = None) -> None:
        res = await self._redis.blpop(self._key, timeout=timeout or 0)  # type: ignore
        if not res:
            raise RedisEventTimeoutError()

    async def clear(self) -> None:
        await self._redis.delete(self._key)  # type: ignore

    async def is_set(self) -> bool:
        length = await self._redis.llen(self._key)  # type: ignore
        return length > 0
