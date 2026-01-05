import asyncio
import time

from aiohttp import ClientSession
from aiohttp.client import _RequestContextManager


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
        print(self.url, self.ttfb, self.ttlb)
        if exc_type is not None:
            import traceback

            traceback.print_exception(exc_type, exc_val, exc_tb)
            # Suppress exceptions raised inside the `async with` block so
            # callers of `LocustClientSession.get()` don't see them.
            return True

        return suppress


class LocustClientSession(ClientSession):
    # explicitly declare this to get the correct return type
    async def __aenter__(self) -> LocustClientSession:
        return self

    def get(self, url, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(super().get(url, **kwargs))


async def user(client: LocustClientSession):
    async with client.get("/charts.webp") as resp:
        assert resp.status == 200


async def main():
    while True:
        async with LocustClientSession("https://www.locust.cloud") as client:
            await user(client)
        await asyncio.sleep(1)


asyncio.run(main())
