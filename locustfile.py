import asyncio
import time

from aiolocust import LocustClientSession, main


# this is for simulating CPU work
def busy_loop(seconds: float):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pass


async def user(client: LocustClientSession):
    async with client.get("http://localhost:8080/index.html") as resp:
        assert resp.status == 200
    # # raise exception (interrupt user) on bad status
    # async with client.get("http://localhost/README2.md", raise_for_status=True) as resp:
    #     pass
    # async with client.get("http://localhost:8080/uv.lock") as resp:
    #     # idk exactly how big uv.lock is, but its gotta be big
    #     assert resp.content_length and resp.content_length > 10000
    # If you want to make things slower/experiment with loadgen performance:
    # busy_loop(0.1)
    # await asyncio.sleep(0.1)


asyncio.run(main(user, 60))
