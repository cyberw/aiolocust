import asyncio
import time

from aiolocust import LocustClientSession, main


def busy_loop(seconds: float):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pass


async def user(client: LocustClientSession):
    async with client.get("https://locust.io/static/img/screenshot_2.31.3-dev_dark.png") as resp:
        assert resp.status == 200
    async with client.get("https://locust.io/") as resp:
        assert resp.status == 200
    busy_loop(1)
    await asyncio.sleep(1)


asyncio.run(main(user, 8))

# limited to 1 thread, note the difference in performance:
# asyncio.run(main(user, 16, 1))
