import asyncio
import threading
import time

from aiohttp import ClientSession
from aiohttp.client import _RequestContextManager


class LocustRequestContextManager:
    def __init__(self, response_cm: _RequestContextManager):
        self.response_cm = response_cm

    async def __aenter__(self):
        self.start_time = time.perf_counter()
        resp = await self.response_cm.__aenter__()
        self.url = self.response_cm._resp.url
        self.ttfb = time.perf_counter() - self.start_time
        await resp.read()
        self.ttlb = time.perf_counter() - self.start_time
        return resp

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        suppress = await self.response_cm.__aexit__(exc_type, exc_val, exc_tb)
        print(self.url, self.ttfb, self.ttlb)
        if exc_type is not None:
            import traceback

            traceback.print_exception(exc_type, exc_val, exc_tb)
            # Suppress exceptions raised inside the `async with` block so
            # callers of `LocustClientSession.get()` don't see them.
            return True

        return suppress


class LocustClientSession(ClientSession):
    # explicitly declare this to get the correct return type
    async def __aenter__(self) -> LocustClientSession:
        return self

    def get(self, url, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(super().get(url, **kwargs))


async def user_runner(user):
    async with LocustClientSession() as client:
        while True:
            await user(client)


def thread_worker(user):
    return asyncio.run(user_runner(user))


async def main(user, concurrency=1):
    threads = []
    for i in range(concurrency):
        t = threading.Thread(target=thread_worker, args=(user,), name=f"WorkerThread-{i}")
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
