class RedisSemaphoreError(Exception):
    """Base exception for redsync errors."""


class RedisSemaphoreCountError(RedisSemaphoreError):
    def __init__(self, count: int) -> None:
        self.count = count
        super().__init__(f"Count must be between 1 and 4096, got {count}")


class RedisSemaphoreNotAcquiredError(RedisSemaphoreError):
    def __init__(self) -> None:
        super().__init__("release() called without acquiring the semaphore")


class RedisSemaphoreTimeoutError(RedisSemaphoreError):
    def __init__(self) -> None:
        super().__init__("Failed to acquire the semaphore")
