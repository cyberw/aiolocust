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

requests = {}


def log_request(url: str, ttfb: float, ttlb: float, success: bool):
    if url not in requests:
        requests[url] = 1, ttfb, ttlb
    else:
        count, total_ttfb, total_ttlb = requests[url]
        requests[url] = (
            count + 1,
            total_ttfb + ttfb,
            total_ttlb + ttlb,
        )
    # print(f"URL: {url}, TTFB: {ttfb:.4f}s, TTLB: {ttlb:.4f}s")


async def stats_printer():
    start_time = time.perf_counter()
    while True:
        await asyncio.sleep(2)
        print("-------------------------------------------------------------------------")
        requests_copy = requests.copy()  # avoid mutation during iteration
        elapsed = time.perf_counter() - start_time
        total_count = 0
        for url, (count, total_ttfb, total_ttlb) in requests_copy.items():
            formatted_url = f"{url:<20}" if len(url) < 20 else url[:17] + "..."
            print(
                f"{formatted_url}: Count: {count}, TTFB: {total_ttfb / count:.2f}s, TTLB: {total_ttlb / count:.2f}s, rate {count / elapsed:.2f} req/s"
            )
            total_count += count
        print(f"Total requests: {total_count}, Overall rate: {total_count / elapsed:.2f} req/s")


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
        success = exc_type is None
        log_request(str(self.url), self.ttfb, self.ttlb, success)
        if not success:
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


async def user_runner(user, count, printer):
    async with asyncio.TaskGroup() as tg:
        if printer:
            tg.create_task(stats_printer())
        for _ in range(count):
            tg.create_task(user_loop(user))


def thread_worker(user, count, printer):
    return asyncio.run(user_runner(user, count, printer))


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
            args=(
                user,
                i,
                not threads,  # first thread prints stats
            ),
        )
        threads.append(t)
        t.start()

    for t in threads:
        t.join()
