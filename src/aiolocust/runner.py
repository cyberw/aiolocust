import asyncio
import os
import signal
import sys
import warnings
from collections.abc import Callable

from aiohttp import ClientResponseError

from aiolocust.http import LocustClientSession
from aiolocust.stats import Stats

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


original_sigint_handler = signal.getsignal(signal.SIGINT)


def distribute_evenly(total, num_buckets) -> list[int]:
    # Calculate the base amount for every bucket
    base = total // num_buckets
    # Calculate how many buckets need an extra +1
    remainder = total % num_buckets
    # Create the list: add 1 to the first 'remainder' buckets
    return [base + 1 if i < remainder else base for i in range(num_buckets)]


class Runner:
    def __init__(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.running = False
        self.start_time = 0
        self.stats = Stats()

    def shutdown(self):
        self.running = False

    async def user_loop(self, user):
        async with LocustClientSession(self.stats.request, self) as client:
            while self.running:
                try:
                    await user(client)
                except (ClientResponseError, AssertionError):
                    pass

    async def user_runner(self, user, count):
        async with asyncio.TaskGroup() as tg:
            for _ in range(count):
                tg.create_task(self.user_loop(user))

    def thread_worker(self, user, count):
        return asyncio.run(self.user_runner(user, count), loop_factory=new_event_loop)

    def signal_handler(self, _sig, _frame):
        print("Stopping...")
        self.running = False
        # stop everything immediately on second Ctrl-C
        signal.signal(signal.SIGINT, original_sigint_handler)

    async def run_test(
        self, user: Callable, user_count: int, duration: int | None = None, event_loops: int | None = None
    ):
        self.running = True
        if event_loops is None:
            if cpu_count := os.cpu_count():
                # for heavy calculations this may need to be increased,
                # but for I/O bound tasks 1/2 of CPU cores seems to be the most efficient
                event_loops = max(cpu_count // 2, 1)
            else:
                event_loops = 1
        loop = asyncio.get_running_loop()
        users_per_worker = distribute_evenly(user_count, event_loops)

        self.stats.reset()

        coros = [asyncio.to_thread(self.thread_worker, user, i) for i in users_per_worker]

        if duration:
            loop.call_later(duration, self.shutdown)

        return await asyncio.gather(*coros)
