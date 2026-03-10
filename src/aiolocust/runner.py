import asyncio
import logging
import os
import signal
import sys
import threading
import warnings

from aiohttp import ClientResponseError
from rich.console import Console

from aiolocust import User, otel, stats

# uvloop is faster than the default pure-python asyncio event loop
# so if it is installed, we're going to be using that one
try:
    import uvloop

    new_event_loop = uvloop.new_event_loop
except ImportError:
    new_event_loop = None

logger = logging.getLogger(__name__)

# Some exceptions will be raised by user code trigger a restart of the run method without propagating it further.
# Gotta do some special logic for Playwright, because it is an optional dependency.
try:
    import playwright.async_api  # pyright: ignore[reportMissingImports]

    EXPECTED_ERRORS = (ClientResponseError, AssertionError, TimeoutError, playwright.async_api.TimeoutError)
except ImportError:
    EXPECTED_ERRORS = (ClientResponseError, AssertionError, TimeoutError)


# We're going to inherit from ClientSession, even though it is considered internal,
# Because we dont want to take the performance hit and typing issues of wrapping every method
warnings.filterwarnings(
    action="ignore",
    message=".*Inheritance .* from ClientSession is discouraged.*",
    category=DeprecationWarning,
    module="aiolocust",
)


if sys._is_gil_enabled():
    # Note: logging has not yet been configured, so it won't get proper formatting
    logger.warning("aiolocust requires a freethreading Python build")


original_sigint_handler = signal.getsignal(signal.SIGINT)


def distribute_evenly(total, num_buckets) -> list[int]:
    # Calculate the base amount for every bucket
    base = total // num_buckets
    # Calculate how many buckets need an extra +1
    remainder = total % num_buckets
    # Create the list: add 1 to the first 'remainder' buckets
    return [base + 1 if i < remainder else base for i in range(num_buckets)]


class LoopWorker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.loop = asyncio.new_event_loop()
        self.running = False

    def run(self):
        self.running = True
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)


class Runner:
    def __init__(self, users: list[type[User]]):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.running = False
        self.start_time = 0
        self.sf = stats.StatsFormatter()
        self.console = Console()
        self.users = users
        self.futures: list[asyncio.Future] = []

    async def stats_printer(self):
        first = True
        while self.running:
            if not first:
                self.console.print(self.sf.get_table())
            first = False
            await asyncio.sleep(2)

    def shutdown(self):
        self.running = False
        for fut in self.futures:
            _ = fut.result()
        otel.logger_provider.shutdown()

    async def user_loop(self, user_class: type[User]):
        user_instance = user_class(runner=self)

        async with user_instance.cm():
            while self.running:
                try:
                    await user_instance.run()
                except EXPECTED_ERRORS:
                    pass  # these errors should already have been recorded by the User
                except Exception as e:
                    stats.record_error(str(e))
                    logger.exception(e)

    def signal_handler(self, _sig, _frame):
        signal.signal(signal.SIGINT, original_sigint_handler)  # stop immediately on second Ctrl-C
        logger.info("\nStopping...")
        self.shutdown()

    def run_test(self, user_count: int, duration: int | None = None, event_loops: int | None = None):
        asyncio.run(self.run_test_async(user_count, duration, event_loops))

    async def run_test_async(self, user_count: int, duration: int | None = None, event_loops: int | None = None):
        self.running = True

        if event_loops is None:
            if cpu_count := os.cpu_count():
                # for heavy calculations this may need to be increased,
                # but for I/O bound tasks 1/2 of CPU cores seems to be the most efficient
                event_loops = max(cpu_count // 2, 1)
            else:
                event_loops = 1

        workers = [LoopWorker() for _ in range(event_loops)]
        for w in workers:
            w.start()

        await asyncio.sleep(0.1)

        for i in range(user_count):
            worker = workers[i % event_loops]
            # Use run_coroutine_threadsafe to cross thread boundaries
            fut = asyncio.run_coroutine_threadsafe(self.user_loop(self.users[0]), worker.loop)
            self.futures.append(fut)  # type: ignore

        loop = asyncio.get_running_loop()
        stats_printer_task = loop.create_task(self.stats_printer())

        if duration:
            loop.call_later(duration, self.shutdown)

        await stats_printer_task

        self.console.print(self.sf.get_table(True))
        if stats.error_counter:
            self.console.print(self.sf.get_error_table())

        for w in workers:
            w.stop()

        return
