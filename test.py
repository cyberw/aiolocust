import asyncio

from aiolocust import LocustClientSession


async def user(client: LocustClientSession):
    async with client.get("/charts.webp") as resp:
        assert resp.status == 200


async def main():
    while True:
        async with LocustClientSession("https://www.locust.cloud") as client:
            await user(client)
        await asyncio.sleep(1)


asyncio.run(main())
