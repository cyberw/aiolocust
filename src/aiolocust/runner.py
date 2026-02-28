import asyncio
import os
import signal
import sys
import traceback
import warnings

from aiohttp import ClientResponseError
from rich.console import Console

from aiolocust import User, stats

# uvloop is faster than the default pure-python asyncio event loop
# so if it is installed, we're going to be using that one
try:
    import uvloop

    new_event_loop = uvloop.new_event_loop
except ImportError:
    new_event_loop = None

# Some exceptions will be raised by user code trigger a restart of the run method without propagating it further.
# Gotta do some special logic for Playwright, because it is an optional dependency.
try:
    import playwright.async_api

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
    raise RuntimeError("aiolocust requires a freethreading Python build")


original_sigint_handler = signal.getsignal(signal.SIGINT)


def distribute_evenly(total, num_buckets) -> list[int]:
    # Calculate the base amount for every bucket
    base = total // num_buckets
    # Calculate how many buckets need an extra +1
    remainder = total % num_buckets
    # Create the list: add 1 to the first 'remainder' buckets
    return [base + 1 if i < remainder else base for i in range(num_buckets)]


class Runner:
    def __init__(self, users: list[type[User]]):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.running = False
        self.start_time = 0
        self.sf = stats.StatsFormatter()
        self.console = Console()
        self.users = users

    async def stats_printer(self):
        first = True
        while self.running:
            if not first:
                self.console.print(self.sf.get_table())
            first = False
            await asyncio.sleep(2)

    def shutdown(self):
        self.running = False
        self.console.print(self.sf.get_table(True))
        if stats.error_counter:
            self.console.print(self.sf.get_error_table())

    async def user_loop(self, user_class: type[User]):
        user_instance = user_class(runner=self)

        async with user_instance.cm():
            while self.running:
                try:
                    await user_instance.run()
                except EXPECTED_ERRORS:
                    pass  # these errors should already have been recorded by the User
                except Exception as e:
                    try:
                        stats.record_error(str(e))
                    except Exception:
                        pass
                    self.console.print("Unhandled exception in user loop:")
                    self.console.print("".join(traceback.format_exception(type(e), e, e.__traceback__)))

    async def user_runner(self, user: type[User], count: int):
        async with asyncio.TaskGroup() as tg:
            for _ in range(count):
                tg.create_task(self.user_loop(user))

    def thread_worker(self, user: type[User], count: int):
        return asyncio.run(self.user_runner(user, count), loop_factory=new_event_loop)

    def signal_handler(self, _sig, _frame):
        print("\nStopping...")
        self.shutdown()
        # stop everything immediately on second Ctrl-C
        signal.signal(signal.SIGINT, original_sigint_handler)

    async def run_test(self, user_count: int, duration: int | None = None, event_loops: int | None = None):
        self.running = True

        if event_loops is None:
            if cpu_count := os.cpu_count():
                # for heavy calculations this may need to be increased,
                # but for I/O bound tasks 1/2 of CPU cores seems to be the most efficient
                event_loops = max(cpu_count // 2, 1)
            else:
                event_loops = 1
        users_per_worker = distribute_evenly(user_count, event_loops)

        coros = [asyncio.to_thread(self.thread_worker, self.users[0], i) for i in users_per_worker]

        loop = asyncio.get_running_loop()
        loop.create_task(self.stats_printer())
        if duration:
            loop.call_later(duration, self.shutdown)

        # Gather worker results but don't cancel siblings on first exception.
        results = await asyncio.gather(*coros, return_exceptions=True)

        # Record and print any exceptions that occurred in worker threads.
        for res in results:
            if isinstance(res, Exception):
                try:
                    stats.record_error(str(res))
                except Exception:
                    pass
                self.console.print("Exception:")
                self.console.print("".join(traceback.format_exception(type(res), res, res.__traceback__)))

        return
