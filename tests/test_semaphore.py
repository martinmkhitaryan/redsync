import asyncio
import multiprocessing
import os
import uuid
from contextlib import asynccontextmanager

import pytest
from redis.asyncio import Redis

from redsync import (
    RedisSemaphore,
    RedisSemaphoreCountError,
    RedisSemaphoreNotAcquiredError,
    RedisSemaphoreTimeoutError,
    SemaphoreInitStrategy,
)

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379")


@asynccontextmanager
async def redis_client(url: str = REDIS_URL):
    client = Redis.from_url(url)
    try:
        yield client
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_async_10_tasks_count_1(semaphore_init_strategy):
    async with redis_client() as redis:
        name = f"test_sem_{uuid.uuid4().hex}"
        results = []

        async def task(tid: int):
            sem = await RedisSemaphore.create(
                redis, name, count=1, semaphore_init_strategy=semaphore_init_strategy
            )
            async with sem:
                results.append(tid)
                await asyncio.sleep(0.01)
                results.append(-tid)

        await asyncio.gather(*(task(i) for i in range(10)))
        assert set(results) == set(range(-9, 10))


@pytest.mark.asyncio
async def test_async_tasks_count_3(semaphore_init_strategy):
    async with redis_client() as redis:
        name = f"test_sem_{uuid.uuid4().hex}"
        results = []

        async def task(tid: int):
            sem = await RedisSemaphore.create(
                redis, name, count=3, semaphore_init_strategy=semaphore_init_strategy
            )
            async with sem:
                print(f"Task {tid} acquired semaphore {name}")
                results.append(tid)
                await asyncio.sleep(0.01)

        await asyncio.gather(*(task(i) for i in range(9)))
        assert set(results) == set(range(9))


def test_multiprocess(semaphore_init_strategy):
    name = f"test_sem_{uuid.uuid4().hex}"
    processes = [
        multiprocessing.Process(
            target=_worker_process,
            args=(name, str(semaphore_init_strategy)),
        )
        for _ in range(10)
    ]
    for proc in processes:
        proc.start()

    for proc in processes:
        proc.join(timeout=30)

    assert all(p.exitcode == 0 for p in processes)


def _worker_process(name: str, strategy: SemaphoreInitStrategy) -> None:
    async def run() -> None:
        async with redis_client(REDIS_URL) as r:
            sem = await RedisSemaphore.create(
                r, name, count=1, semaphore_init_strategy=strategy
            )
            async with sem:
                print(f"Worker {os.getpid()} acquired semaphore {name}")
                pass

    asyncio.run(run())


@pytest.mark.asyncio
@pytest.mark.parametrize("count", [0, -1, 42000])
async def test_count_error(count):
    async with redis_client() as redis:
        name = f"test_sem_{uuid.uuid4().hex}"
        with pytest.raises(RedisSemaphoreCountError) as exc_info:
            await RedisSemaphore.create(redis, name, count=count)
        assert exc_info.value.count == count


@pytest.mark.asyncio
async def test_not_acquired_error(semaphore_init_strategy):
    async with redis_client() as redis:
        name = f"test_sem_{uuid.uuid4().hex}"
        sem = await RedisSemaphore.create(
            redis, name, count=1, semaphore_init_strategy=semaphore_init_strategy
        )
        with pytest.raises(RedisSemaphoreNotAcquiredError):
            await sem.release()


@pytest.mark.asyncio
async def test_timeout_error(semaphore_init_strategy):
    async with redis_client() as redis:
        name = f"test_sem_{uuid.uuid4().hex}"
        sem = await RedisSemaphore.create(
            redis, name, count=1, semaphore_init_strategy=semaphore_init_strategy
        )
        await sem.acquire()
        with pytest.raises(RedisSemaphoreTimeoutError):
            await sem.acquire(timeout=0.05)

        await sem.release()
