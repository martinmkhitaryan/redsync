class RedsyncError(Exception):
    """Base exception for redsync errors."""


class RedisSemaphoreError(RedsyncError):
    """Base exception for semaphore related errors."""


class RedisSemaphoreCountError(RedisSemaphoreError):
    def __init__(self, count: int) -> None:
        self.count = count
        super().__init__(f"Count must be between 1 and 4096, got {count}")


class RedisSemaphoreCountMismatchError(RedisSemaphoreError):
    def __init__(self, requested: int, actual: int) -> None:
        self.requested = requested
        self.actual = actual
        super().__init__(
            f"Requested count {requested} does not match existing count {actual}"
        )


class RedisSemaphoreNotAcquiredError(RedisSemaphoreError):
    def __init__(self) -> None:
        super().__init__("release() called without acquiring the semaphore")


class RedisSemaphoreTimeoutError(RedisSemaphoreError):
    def __init__(self) -> None:
        super().__init__("Failed to acquire the semaphore")


class RedisEventError(RedsyncError):
    """Base exception for event related errors."""


class RedisEventTimeoutError(RedisEventError):
    def __init__(self) -> None:
        super().__init__("Timed out waiting for the event")
