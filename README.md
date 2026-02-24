# redsync

[![PyPI version](https://img.shields.io/pypi/v/redsync)](https://pypi.org/project/redsync/)
[![codecov](https://codecov.io/gh/martinmkhitaryan/redsync/graph/badge.svg)](https://codecov.io/gh/martinmkhitaryan/redsync)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Redis-based distributed synchronization primitives for Python.** Async API using `redis.asyncio`.

## Features

- **Blocking, no polling** – Uses Redis `BLPOP`: the connection blocks on the server until a permit is available. No busy-waiting, no lock + pub/sub overhead.
- **Async-first** – Built on `redis.asyncio`; use with `async`/`await` and context managers.
- **Configurable init** – LUA (atomic, default) or SETNX strategy for creating the permit pool.
- **N permits** – Semaphore count from 1 to 4096 for limiting concurrency across processes.
- **Python 3.10+** – Modern Python support.

## TODO

- [ ] **Semaphore delete / lifecycle**
  - Option A: set expire time on the list key (simple; semaphore disappears when unused).
  - Option B: async background task that extends TTL while at least one semaphore instance exists (keeps it alive as long as someone uses it).
  - Consider other algorithms (e.g. refcount in metadata, lease-based cleanup).
- [ ] **Creator-only count** – Only the creator sets `count`; other callers wait until the semaphore exists and then read metadata (count, etc.) instead of passing count.
- [ ] **Maybe List vs sorted set** – Evaluate whether Redis sorted sets are a better fit than a list (e.g. per-permit TTL, ordering, or different blocking semantics).
- [ ] **Other sync primitives** – Add more primitives (e.g. event).

## Installation

```bash
pip install redsync
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv add redsync
```

**Requirements:** Redis server, `redis>=5.0.0` (async support).

## Semaphore

### Usage

```python
import asyncio
from redis.asyncio import Redis
from redsync import RedisSemaphore, RedisSemaphoreTimeoutError

async def main():
    r = Redis()
    sem = await RedisSemaphore.create(r, "my_resource", count=1)

    # acquire() raises RedisSemaphoreTimeoutError on timeout
    try:
        await sem.acquire(timeout=10)
        try:
            # do work
            pass
        finally:
            await sem.release()
    except RedisSemaphoreTimeoutError:
        pass  # handle timeout

    # or use context manager (raises on timeout)
    async with sem:
        # do work
        pass

asyncio.run(main())
```

### N permits

Use `count > 1` to allow N concurrent holders. `count` must be between 1 and 4096.

```python
from redsync import SemaphoreInitStrategy

sem = await RedisSemaphore.create(r, "pool", count=5, semaphore_init_strategy=SemaphoreInitStrategy.LUA)
await sem.acquire()
# ...
await sem.release()
```

## Init strategies

The semaphore uses a Redis list as a permit pool. The list must be created and filled with `count` elements before anyone can `BLPOP`. Two strategies are supported:

| | **Lua** | **SETNX** |
|---|--------|--------|
| **Idea** | Run a script that atomically ensures the list has N elements (if `LLEN == 0` then `RPUSH` N times). | Use a separate init key; the first process that wins `SET NX` creates the list and pushes N elements, then deletes the init key. |
| **Pros** | Single atomic op; no extra key; no crash race during init; idempotent. | No Lua; only basic commands; easy to debug in Redis. |
| **Cons** | Requires Lua (standard in Redis). | Extra key; two round-trips for the initializer (SETNX then RPUSH). |

Default is `SemaphoreInitStrategy.LUA`. Use `SemaphoreInitStrategy.SETNX` to avoid Lua.

## Exceptions

- `RedisSemaphoreError` - Base exception
- `RedisSemaphoreTimeoutError` – `acquire()` timed out
- `RedisSemaphoreNotAcquiredError` – `release()` called without acquiring
- `RedisSemaphoreCountError` – `count` not in 1–4096

## API Reference

### RedisSemaphore

```python
class RedisSemaphore:
    @classmethod
    async def create(cls, redis_client, name: str, *, count: int = 1,
                    semaphore_init_strategy: SemaphoreInitStrategy = SemaphoreInitStrategy.LUA,
                    key_prefix: str = "redis_semaphore") -> RedisSemaphore

    async def acquire(self, timeout: float | None = None) -> None  # None = block until available
    async def release(self) -> None
    async def __aenter__(self) -> RedisSemaphore
    async def __aexit__(...) -> None
```

- **name** – Semaphore identifier (shared across processes).
- **count** – Number of permits (1–4096).
- **timeout** – For `acquire()`: seconds to wait; `None` blocks indefinitely. Raises `RedisSemaphoreTimeoutError` on timeout.

## Running tests

```bash
pytest
# or
uv run pytest
```

Set `REDIS_URL` if Redis is not on `localhost:6379`.

## License

MIT License – see [LICENSE](LICENSE).
