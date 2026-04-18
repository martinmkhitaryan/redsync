import pytest

from redsync import SemaphoreInitStrategy


@pytest.fixture(
    params=[SemaphoreInitStrategy.LUA, SemaphoreInitStrategy.OPTIMISTIC_LOCKING]
)
def semaphore_init_strategy(request):
    return request.param
