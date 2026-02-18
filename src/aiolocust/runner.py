import asyncio
import os
import signal
import sys
import warnings
from collections.abc import Callable

from aiohttp import ClientResponseError
from rich.console import Console

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


class Worker:
    def __init__(self, runner: Runner, user: Callable):
        self._runner = runner
        self._user = user

        self._loop: asyncio.AbstractEventLoop | None = None

        self._tasks: list[asyncio.Task] = []
        self._pending_spawns = 0

    async def _user_loop(self) -> None:
        async with LocustClientSession(self._runner.stats.request, self._runner) as client:
            while self._runner.running:
                try:
                    await self._user(client)
                except (ClientResponseError, AssertionError):
                    pass

    async def _launch_users(self, n: int) -> None:
        for _ in range(n):
            self._tasks.append(asyncio.create_task(self._user_loop()))

    def launch_more(self, n: int) -> None:
        if n <= 0:
            return

        self._pending_spawns += n

        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._drain_spawns)

    def _drain_spawns(self) -> None:
        n = self._pending_spawns

        if n > 0:
            asyncio.create_task(self._launch_users(n))
            self._pending_spawns = 0

    async def _entrypoint(self) -> None:
        self._loop = asyncio.get_running_loop()

        self._drain_spawns()

        while self._runner.running:
            await asyncio.sleep(0.1)

        await asyncio.gather(*self._tasks)

    def start(self) -> None:
        asyncio.run(self._entrypoint(), loop_factory=new_event_loop)


class Runner:
    def __init__(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.running = False
        self.start_time = 0
        self.stats = Stats()
        self.console = Console()

    async def stats_printer(self):
        first = True
        while self.running:
            if not first:
                self.console.print(self.stats.get_table())
            first = False
            await asyncio.sleep(2)

    def shutdown(self):
        self.running = False
        self.console.print(self.stats.get_table(True))
        if self.stats.error_counter:
            self.console.print(self.stats.get_error_table())

    def signal_handler(self, _sig, _frame):
        print("\nStopping...")
        self.shutdown()
        # stop everything immediately on second Ctrl-C
        signal.signal(signal.SIGINT, original_sigint_handler)

    async def run_test(
        self,
        user: Callable,
        user_count: int,
        spawn_rate: float | None = None,
        duration: int | None = None,
        event_loops: int | None = None,
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

        workers = [Worker(self, user) for _ in range(event_loops)]
        worker_tasks = [asyncio.create_task(asyncio.to_thread(w.start)) for w in workers]

        loop.create_task(self.stats_printer())

        if not spawn_rate:
            spawn_rate = user_count

        remaining = user_count
        rr = 0
        # take into account user fractions
        budget = 0.0

        tick = 1.0
        while remaining > 0:
            budget += spawn_rate * tick
            to_spawn = min(int(budget), remaining)

            # round-robin
            for _ in range(to_spawn):
                workers[rr].launch_more(1)
                rr = (rr + 1) % len(workers)

            budget -= to_spawn
            remaining -= to_spawn

            await asyncio.sleep(tick)

        if duration:
            loop.call_later(duration, self.shutdown)

        await asyncio.gather(*worker_tasks)

        return
