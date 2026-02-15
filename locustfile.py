import asyncio

from aiolocust import LocustClientSession


async def run(client: LocustClientSession):
    async with client.get("http://localhost:8080/") as resp:
        pass
    async with client.get("http://localhost:8080/") as resp:
        assert "Example" in await resp.text()
    await asyncio.sleep(0.1)


# see examples/advanced.py for more
