# redsync

[![PyPI version](https://img.shields.io/pypi/v/redsync)](https://pypi.org/project/redsync/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Redis-based distributed synchronization primitives for Python.** Async API using `redis.asyncio`.

## Features

- **Blocking, no polling** – Uses Redis `BLPOP`: the connection blocks on the server until a permit is available. No busy-waiting, no lock + pub/sub overhead.
- **Async-first** – Built on `redis.asyncio`; use with `async`/`await` and context managers.
- **Configurable init** – LUA (atomic, default) or OPTIMISTIC_LOCKING strategy for creating the permit pool.
- **N permits** – Semaphore count from 1 to 4096 for limiting concurrency across processes.
- **Automatic lifecycle** – Built-in watchdog with lease extension keeps semaphores alive while in use; Redis auto-deletes keys when all clients disconnect or crash.
- **Python 3.10+** – Modern Python support.

## TODO

- [ ] **Automatic leaked permit recovery** – Implement a mechanism (e.g. via heartbeats in metadata) to detect and reclaim permits that were leaked because a worker crashed while holding them.
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

### N permits and attaching

Use `count > 1` to allow N concurrent holders. `count` must be between 1 and 4096.

```python
from redsync import SemaphoreInitStrategy

# Creator initializes the pool
sem = await RedisSemaphore.create(r, "pool", count=5, semaphore_init_strategy=SemaphoreInitStrategy.LUA)

# Other workers can attach without knowing the count
worker_sem = await RedisSemaphore.attach(r, "pool", timeout=60.0)
print(f"Total permits: {await worker_sem.get_count()}")

await worker_sem.acquire()
# ...
await worker_sem.release()
```

### `create` vs `attach`

In a distributed environment, you have two options for connecting to a semaphore:

1. **Call `create()` everywhere (Idempotent):** If your application consists of multiple identical worker nodes running the exact same codebase, they can all safely call `RedisSemaphore.create(..., count=5)`. The first worker to execute it will atomically initialize the semaphore, and the rest will instantly validate that their requested count matches the existing one. 
2. **Call `create()` once, and `attach()` elsewhere (Consumer):** If your architecture has a central "manager" process that dictates concurrency limits, the manager calls `create(..., count=5)`. The worker processes then call `RedisSemaphore.attach(..., timeout=60.0)`. `attach()` does not require a `count`, never initializes the pool, and simply polls until the creator sets it up.

**Semantic Intent:**
While using `create()` everywhere works perfectly, using `attach()` cleanly separates your **Control Plane** (the entity that decides the concurrency limits and creates the resources) from your **Data Plane** (the workers that just consume the resources). It simplifies worker code because workers do not need to hardcode or know the count beforehand—they just say *"Give me a permit for the pool the manager set up."*

## Init strategies

The semaphore uses a Redis list as a permit pool. The list must be created and filled with `count` elements before anyone can `BLPOP`. Two strategies are supported:

| | **Lua** | **Optimistic Locking** |
|---|--------|--------|
| **Idea** | Run a script that atomically ensures the list has N elements (if `LLEN == 0` then `RPUSH` N times). | Uses a Redis transaction (`WATCH` + `MULTI/EXEC`) to atomically check if the metadata exists, and if not, creates the list and metadata. |
| **Pros** | Single atomic op; no extra key; idempotent. | No Lua; perfectly atomic; crash-proof. |
| **Cons** | Requires Lua (standard in Redis). | Transaction retry loop in Python code. |

Default is `SemaphoreInitStrategy.LUA`. Use `SemaphoreInitStrategy.OPTIMISTIC_LOCKING` to avoid Lua.

## Lifecycle (Watchdog)

Every `RedisSemaphore` instance runs a background **watchdog** task that periodically extends the TTL of the underlying Redis keys. This ensures:

- **Keys stay alive** as long as at least one client holds a reference to the semaphore.
- **Automatic cleanup** when all clients disconnect or crash — Redis expires the keys after `lease_ttl` seconds with no renewals.
- **No thundering herd** — each watchdog adds random jitter to its renewal interval so multiple clients don't all hit Redis at the same instant.

| Parameter | Default | Description |
|-----------|---------|-------------|
| `lease_ttl` | `300.0` (5 min) | TTL set on Redis keys. The watchdog renews every `lease_ttl / 3` seconds (±20% jitter). |

```python
# Custom lease TTL
sem = await RedisSemaphore.create(r, "my_resource", count=3, lease_ttl=120.0)

# Always close when done to stop the watchdog immediately
await sem.close()
```

If `close()` is not called (e.g. process crash), the keys will naturally expire after `lease_ttl` seconds.

## Exceptions

- `RedisSemaphoreError` - Base exception
- `RedisSemaphoreTimeoutError` – `acquire()` or `attach()` timed out
- `RedisSemaphoreNotAcquiredError` – `release()` called without acquiring
- `RedisSemaphoreCountError` – `count` not in 1–4096
- `RedisSemaphoreCountMismatchError` – `create()` was called with a count that doesn't match the existing semaphore count

## API Reference

### RedisSemaphore

```python
class RedisSemaphore:
    @classmethod
    async def create(cls, redis_client, name: str, *, count: int = 1,
                    lease_ttl: float = 300.0,
                    semaphore_init_strategy: SemaphoreInitStrategy = SemaphoreInitStrategy.LUA,
                    key_prefix: str = "redis_semaphore") -> RedisSemaphore

    @classmethod
    async def attach(cls, redis_client, name: str, *, timeout: float | None = 60.0,
                    lease_ttl: float = 300.0,
                    key_prefix: str = "redis_semaphore") -> RedisSemaphore

    async def get_count(self) -> int | None

    async def acquire(self, timeout: float | None = None) -> None  # None = block until available
    async def release(self) -> None
    async def close(self) -> None  # Stop the watchdog task
    async def __aenter__(self) -> RedisSemaphore
    async def __aexit__(...) -> None
```

- **name** – Semaphore identifier (shared across processes).
- **count** – Number of permits (1–4096).
- **lease_ttl** – TTL in seconds for Redis keys; the watchdog renews every `lease_ttl / 3` seconds.
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
