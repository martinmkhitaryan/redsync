import asyncio
import os
import uuid
from contextlib import asynccontextmanager

import pytest
from redis.asyncio import Redis

from redsync import RedisEvent, RedisEventTimeoutError

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


@asynccontextmanager
async def redis_client(url: str = REDIS_URL):
    client = Redis.from_url(url)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_event_basic():
    async with redis_client() as redis:
        name = f"test_event_{uuid.uuid4().hex}"
        event = RedisEvent(redis, name)

        assert not await event.is_set()

        await event.set()
        assert await event.is_set()

        await event.wait(timeout=1)
        assert not await event.is_set()


@pytest.mark.asyncio
async def test_event_timeout():
    async with redis_client() as redis:
        name = f"test_event_{uuid.uuid4().hex}"
        event = RedisEvent(redis, name)

        with pytest.raises(RedisEventTimeoutError):
            await event.wait(timeout=0.1)


@pytest.mark.asyncio
async def test_event_clear():
    async with redis_client() as redis:
        name = f"test_event_{uuid.uuid4().hex}"
        event = RedisEvent(redis, name)

        await event.set()
        await event.set()
        assert await event.is_set()

        await event.clear()
        assert not await event.is_set()


@pytest.mark.asyncio
async def test_event_order():
    async with redis_client() as redis:
        name = f"test_event_{uuid.uuid4().hex}"
        event = RedisEvent(redis, name)
        results = []

        async def waiter(tid):
            await event.wait()
            results.append(tid)

        # Start two waiters
        t1 = asyncio.create_task(waiter(1))
        t2 = asyncio.create_task(waiter(2))
        await asyncio.sleep(0.1)

        await event.set()
        await asyncio.sleep(0.1)
        assert len(results) == 1

        await event.set()
        await asyncio.sleep(0.1)
        assert len(results) == 2
        assert set(results) == {1, 2}

        await asyncio.gather(t1, t2)


@pytest.mark.asyncio
async def test_event_pre_set():
    async with redis_client() as redis:
        name = f"test_event_{uuid.uuid4().hex}"
        event = RedisEvent(redis, name)

        await event.set()
        # Should return immediately
        await event.wait(timeout=0.1)
        assert not await event.is_set()
