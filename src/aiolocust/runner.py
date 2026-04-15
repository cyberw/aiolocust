import asyncio
import logging
import math
import os
import signal
import sys
import threading
import time
import warnings

from aiohttp import ClientOSError
from rich.console import Console

from aiolocust import User, otel, stats
from aiolocust.datatypes import SafeCounter, Stage

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

    EXPECTED_ERRORS = (ClientOSError, AssertionError, TimeoutError, playwright.async_api.TimeoutError)
except ImportError:
    EXPECTED_ERRORS = (ClientOSError, AssertionError, TimeoutError)


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


def desired_user_count(stages: list[Stage], elapsed: float) -> int | None:
    total_time = 0.0
    previous_user_count = 0
    for stage in stages:
        total_time += stage.duration
        if elapsed <= total_time:
            time_left_in_stage = total_time - elapsed
            return math.ceil(
                previous_user_count + (stage.target - previous_user_count) * (1 - time_left_in_stage / stage.duration)
            )
        previous_user_count = stage.target

    return None


class LoopWorker(threading.Thread):
    def __init__(self):
        super().__init__(daemon=True)
        self.loop = asyncio.new_event_loop()

    def run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)


class Runner:
    def __init__(
        self,
        users: list[type[User]],
        user_count: int = 1,
        duration: int | None = None,
        rate: float | None = None,
        iterations: int | None = None,
        host: str | None = None,
        config: dict | None = None,
        event_loops: int | None = None,
    ):
        signal.signal(signal.SIGINT, self.signal_handler)
        self.running = False
        self.start_time = 0
        self.sf = stats.StatsFormatter()
        self.console = Console()
        self.users = users
        self.host = host
        self.iteration_counter = SafeCounter(iterations)
        config = config or {}

        if "stages" in config:
            self.stages = [Stage(**item) for item in config["stages"]]
            if user_count > 1 or duration or rate:
                logger.info("Both stages and user_count/duration/rate were specified, stages will take precedence")
        else:
            ramp_up_time = user_count / rate if rate else 0
            self.stages = [
                Stage(ramp_up_time, user_count),
                Stage(duration - ramp_up_time if duration else 99999999, user_count),
            ]

        logger.debug(f"Stages: {self.stages}")

        if event_loops is None:
            if cpu_count := os.cpu_count():
                # for heavy calculations this may need to be increased,
                # but for I/O bound tasks 1/2 of CPU cores seems to be very efficient
                self.event_loops = max(cpu_count // 2, 1)
            else:
                self.event_loops = 1
        else:
            self.event_loops = event_loops
        self.running_users: set[User] = set()
        self.futures: list[asyncio.Future] = []

    async def stats_printer(self):
        first = True
        while self.running:
            if not first:
                self.console.print(self.sf.get_table())
            first = False
            await asyncio.sleep(2)

    def shutdown(self):
        logger.debug("Shutting down...")
        if not self.running:
            logger.debug("Already shutting down, ignoring shutdown() call")
            return
        self.running = False
        for user in self.running_users:
            user.running = False
        for fut in self.futures:
            _ = fut.result()
        otel.logger_provider.shutdown()

    async def user_loop(self, user_instance: User):
        async with user_instance.cm():
            while user_instance.running:
                if self.iteration_counter.increment():
                    user_instance.running = False
                    self.running_users.remove(user_instance)
                    if not self.running_users:
                        logger.debug(f"Reached iteration limit ({self.iteration_counter.value}) & all users finished")
                        self.shutdown()
                    break
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

    def run_test(self):
        asyncio.run(self.run_test_async())

    def add_user(self, worker: LoopWorker):
        user = self.users[0](self)
        self.running_users.add(user)
        fut = asyncio.run_coroutine_threadsafe(self.user_loop(user), worker.loop)
        self.futures.append(fut)  # type: ignore

    def stop_user(self):
        user = self.running_users.pop()
        user.running = False

    async def run_test_async(self):
        self.running = True

        workers = [LoopWorker() for _ in range(self.event_loops)]
        for w in workers:
            w.start()
        logger.debug(f"Running with {self.event_loops} event loops")
        await asyncio.sleep(0.1)

        loop = asyncio.get_running_loop()
        stats_printer_task = loop.create_task(self.stats_printer())

        self.start_time = time.time()
        self.previous_user_count = 0

        while self.running:
            await asyncio.sleep(0.01)
            elapsed = time.time() - self.start_time
            new_user_count = desired_user_count(self.stages, elapsed)
            if new_user_count is None:
                break
            change = new_user_count - self.previous_user_count
            if change > 0:
                for i in range(change):
                    worker = workers[(i + self.previous_user_count) % self.event_loops]
                    self.add_user(worker)
            elif change < 0:
                for i in range(-change):
                    self.stop_user()
            self.previous_user_count = new_user_count

        if self.running:  # if we exited the loop without a signal, we should still do a proper shutdown
            self.shutdown()

        stats_printer_task.cancel()

        self.console.print(self.sf.get_table(True))
        if stats.error_counter:
            self.console.print(self.sf.get_error_table())

        for w in workers:
            w.stop()

        return
