import asyncio
import random

from aiolocust import LocustClientSession, main


async def user(client: LocustClientSession):
    for i in range(20000000):
        _ = i + 1  # use some cpu!
    async with client.get("https://locust.io/static/img/screenshot_2.31.3-dev_dark.png") as resp:
        assert resp.status == 200
    await asyncio.sleep(random.uniform(0.1, 1.0))


asyncio.run(main(user, 16))

# limited to 1 thread, note the difference in performance:
# asyncio.run(main(user, 16, 1))
