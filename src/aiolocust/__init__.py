import asyncio
import os
import sys
import threading
import time
from collections.abc import Callable

from aiohttp import ClientSession
from aiohttp.client import _RequestContextManager

if sys._is_gil_enabled():
    raise RuntimeError("aiolocust requires a freethreading Python build")


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
    iteration = 0

    # explicitly declare this to get the correct return type
    async def __aenter__(self) -> LocustClientSession:
        return self

    def get(self, url, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(super().get(url, **kwargs))

    def post(self, url, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(super().post(url, **kwargs))


async def user_loop(user):
    async with LocustClientSession() as client:
        while True:
            await user(client)
            client.iteration += 1


async def user_runner(user, count):
    async with asyncio.TaskGroup() as tg:
        for _ in range(count):
            tg.create_task(user_loop(user))


def thread_worker(user, count):
    return asyncio.run(user_runner(user, count))


def distribute_evenly(total, num_buckets):
    # Calculate the base amount for every bucket
    base = total // num_buckets
    # Calculate how many buckets need an extra +1
    remainder = total % num_buckets
    # Create the list: add 1 to the first 'remainder' buckets
    return [base + 1 if i < remainder else base for i in range(num_buckets)]


async def main(user: Callable, user_count: int, concurrency: int | None = None):
    if concurrency is None:
        concurrency = os.cpu_count() or 1

    threads = []
    for i in distribute_evenly(user_count, concurrency):
        t = threading.Thread(
            target=thread_worker,
            args=(user, i),
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
