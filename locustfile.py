import asyncio

from aiolocust import HttpUser


async def run(self: HttpUser):
    async with self.client.get("http://localhost:8080/") as resp:
        pass
    async with self.client.get("http://localhost:8080/") as resp:
        assert "Example" in await resp.text()
    await asyncio.sleep(0.1)


# See examples/advanced.py for more
#
# If you're not already familiar with using aiohttp to make http calls, see https://docs.aiohttp.org/
