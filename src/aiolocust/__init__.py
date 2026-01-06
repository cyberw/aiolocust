import asyncio
import os
import sys
import threading
import time
from collections.abc import Callable

# uvloop is faster than the default pure-python asyncio event loop
# so we're going to be using that one
import uvloop
from aiohttp import ClientSession
from aiohttp.client import _RequestContextManager

if sys._is_gil_enabled():
    raise RuntimeError("aiolocust requires a freethreading Python build")


requests = {}
running = True

from rich.console import Console
from rich.table import Table

console = Console()


def log_request(url: str, ttfb: float, ttlb: float, success: bool):
    if url not in requests:
        requests[url] = 1, ttfb, ttlb, ttlb
    else:
        count, sum_ttfb, sum_ttlb, max_ttlb = requests[url]
        requests[url] = (
            count + 1,
            sum_ttfb + ttfb,
            sum_ttlb + ttlb,
            max(max_ttlb, ttlb),
        )
    # print(f"URL: {url}, TTFB: {ttfb:.4f}s, TTLB: {ttlb:.4f}s")


async def stats_printer():
    global running
    start_time = time.perf_counter()
    while running:
        await asyncio.sleep(2)
        requests_copy = requests.copy()  # avoid mutation during print
        elapsed = time.perf_counter() - start_time
        total_ttlb = 0
        total_max_ttlb = 0
        total_count = 0
        table = Table(show_edge=False)
        table.add_column("Name", max_width=30)
        table.add_column("Avg", justify="right")
        table.add_column("Max", justify="right")
        table.add_column("Count", justify="right")
        table.add_column("Rate", justify="right")
        for url, (count, ttfb, ttlb, max_ttlb) in requests_copy.items():
            table.add_row(
                url,
                f"{1000 * ttlb / count:4.1f}ms",
                f"{1000 * max_ttlb:4.1f}ms",
                str(count),
                f"{count / elapsed:.2f}/s",
            )
            total_ttlb += ttlb
            total_max_ttlb = max(total_max_ttlb, max_ttlb)
            total_count += count
        table.add_section()
        table.add_row(
            "Total",
            f"{1000 * total_ttlb / total_count:4.1f}ms",
            f"{1000 * total_max_ttlb:4.1f}ms",
            str(total_count),
            f"{total_count / elapsed:.2f}/s",
        )
        print()
        console.print(table)

        if elapsed > 30:
            running = False


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
        while running:
            await user(client)
            client.iteration += 1


async def user_runner(user, count, printer):
    async with asyncio.TaskGroup() as tg:
        if printer:
            tg.create_task(stats_printer())
        for _ in range(count):
            tg.create_task(user_loop(user))


def thread_worker(user, count, printer):
    run = asyncio.run(user_runner(user, count, printer), loop_factory=uvloop.new_event_loop)
    asyncio.get_event_loop().set_debug(False)
    return run


def distribute_evenly(total, num_buckets):
    # Calculate the base amount for every bucket
    base = total // num_buckets
    # Calculate how many buckets need an extra +1
    remainder = total % num_buckets
    # Create the list: add 1 to the first 'remainder' buckets
    return [base + 1 if i < remainder else base for i in range(num_buckets)]


async def main(user: Callable, user_count: int, event_loops: int | None = None):
    if event_loops is None:
        if cpu_count := os.cpu_count():
            # for heavy calculations this may need to be increased,
            # but for I/O bound tasks 1/2 of CPU cores seems to be the most efficient
            event_loops = max(cpu_count // 2, 1)
        else:
            event_loops = 1

    threads = []
    for i in distribute_evenly(user_count, event_loops):
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
