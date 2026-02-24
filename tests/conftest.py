import pytest

from redsync import SemaphoreInitStrategy


@pytest.fixture(params=[SemaphoreInitStrategy.LUA, SemaphoreInitStrategy.SETNX])
def semaphore_init_strategy(request):
    return request.param
