import asyncio
import os
import signal
import sys
import threading
import time
import warnings
from collections.abc import Callable

from aiohttp import ClientConnectorError, ClientResponse, ClientResponseError, ClientSession
from aiohttp.client import _RequestContextManager
from rich.console import Console
from rich.table import Table

from . import event_handlers
from .datatypes import Request, RequestEntry

# uvloop is faster than the default pure-python asyncio event loop
# so if it is installed, we're going to be using that one
try:
    import uvloop

    new_event_loop = uvloop.new_event_loop
except ImportError:
    new_event_loop = None

# We're going to inherit from ClientSession, even though it is considered internal,
# Because we dont want to take the performance hit and typing issues of wrapping every method
warnings.filterwarnings(
    action="ignore",
    message=".*Inheritance .* from ClientSession is discouraged.*",
    category=DeprecationWarning,
    module="aiolocust",
)

if sys._is_gil_enabled():
    raise RuntimeError("aiolocust requires a freethreading Python build")


running = True
console = Console()


original_sigint_handler = signal.getsignal(signal.SIGINT)


def signal_handler(_sig, _frame):
    print("Stopping...")
    global running
    running = False
    # stop everything immediately on second Ctrl-C
    signal.signal(signal.SIGINT, original_sigint_handler)


signal.signal(signal.SIGINT, signal_handler)


async def stats_printer():
    global running
    start_time = time.perf_counter()
    while running:
        await asyncio.sleep(2)
        requests_copy: dict[str, RequestEntry] = (
            event_handlers.requests.copy()
        )  # avoid mutation during print
        elapsed = time.perf_counter() - start_time
        total_ttlb = 0
        total_max_ttlb = 0
        total_count = 0
        total_errorcount = 0
        table = Table(show_edge=False)
        table.add_column("Name", max_width=30)
        table.add_column("Count", justify="right")
        table.add_column("Failures", justify="right")
        table.add_column("Avg", justify="right")
        table.add_column("Max", justify="right")
        table.add_column("Rate", justify="right")

        for url, re in requests_copy.items():
            table.add_row(
                url,
                str(re.count),
                f"{re.errorcount} ({100 * re.errorcount / re.count:2.1f}%)",
                f"{1000 * re.sum_ttlb / re.count:4.1f}ms",
                f"{1000 * re.max_ttlb:4.1f}ms",
                f"{re.count / elapsed:.2f}/s",
            )
            total_ttlb += re.sum_ttlb
            total_max_ttlb = max(total_max_ttlb, re.max_ttlb)
            total_count += re.count
            total_errorcount += re.errorcount
        table.add_section()
        table.add_row(
            "Total",
            str(total_count),
            f"{total_errorcount} ({100 * total_errorcount / total_count:2.1f}%)",
            f"{1000 * total_ttlb / total_count:4.1f}ms",
            f"{1000 * total_max_ttlb:4.1f}ms",
            f"{total_count / elapsed:.2f}/s",
        )
        print()
        console.print(table)

        if elapsed > 30:
            running = False


class LocustRequestContextManager(_RequestContextManager):
    def __init__(self, request_handler: Callable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # slightly hacky way to get the URL, but passing it explicitly would be a mess
        # and it is only used for connection errors where the exception doesn't contain URL
        self.str_or_url = args[0]._coro.cr_frame.f_locals["str_or_url"]
        self.request_handler = request_handler
        self.force_success = False

    async def __aenter__(self):
        self.start_time = time.perf_counter()
        try:
            await super().__aenter__()
        except ClientConnectorError as e:
            elapsed = self.ttlb = time.perf_counter() - self.start_time
            if request_info := getattr(e, "request_info", None):
                url = request_info.url
            else:
                url = self.str_or_url
            self.request_handler(Request(url, elapsed, elapsed, False))
            raise
        except ClientResponseError as e:
            elapsed = self.ttlb = time.perf_counter() - self.start_time
            self.request_handler(Request(str(e.request_info.url), elapsed, elapsed, False))
            raise
        else:
            self.url = super()._resp.url
            self.ttfb = time.perf_counter() - self.start_time
            await self._resp.read()
            self.ttlb = time.perf_counter() - self.start_time
        return self._resp

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool | None:
        suppress = await super().__aexit__(exc_type, exc_val, exc_tb)
        self.request_handler(
            Request(
                str(self.url),
                self.ttfb,
                self.ttlb,
                self.force_success or exc_val is None and not self._resp.status >= 400,
            )
        )

        return suppress


class LocustClientSession(ClientSession):
    iteration = 0

    def __init__(self, base_url=None, request_handler: Callable | None = None, **kwargs):
        super().__init__(base_url=base_url, **kwargs)
        self.request_handler = request_handler or event_handlers.request

    # explicitly declare this to get the correct return type and enter session
    async def __aenter__(self) -> LocustClientSession:
        return self

    def get(self, url, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(self.request_handler, super().get(url, **kwargs))

    def post(self, url, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(self.request_handler, super().post(url, **kwargs))


async def user_loop(user):
    async with LocustClientSession() as client:
        while running:
            try:
                await user(client)
            except (ClientResponseError, AssertionError):
                pass
            client.iteration += 1


async def user_runner(user, count, printer):
    event_handlers.requests = {}
    async with asyncio.TaskGroup() as tg:
        if printer:
            tg.create_task(stats_printer())
        for _ in range(count):
            tg.create_task(user_loop(user))


def thread_worker(user, count, printer):
    return asyncio.run(user_runner(user, count, printer), loop_factory=new_event_loop)


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
