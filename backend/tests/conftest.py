import asyncio
from concurrent.futures import ThreadPoolExecutor

import anyio.to_thread
import pytest


@pytest.fixture(scope="session", autouse=True)
def patch_anyio_threadpool():
    executor = ThreadPoolExecutor(max_workers=8)

    async def run_sync(func, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))

    original = anyio.to_thread.run_sync
    anyio.to_thread.run_sync = run_sync
    yield
    anyio.to_thread.run_sync = original
    executor.shutdown(wait=True)
