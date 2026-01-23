import time

from aiolocust import LocustClientSession


# this is for simulating CPU work
def busy_loop(seconds: float):
    end = time.perf_counter() + seconds
    while time.perf_counter() < end:
        pass


async def run(client: LocustClientSession):
    async with client.get("http://localhost:8080/") as resp:
        pass
    async with client.get("http://localhost:8080/doesnt_exist", raise_for_status=True) as resp:
        pass

    # # raise exception (interrupt user) on bad status
    # async with client.get("http://localhost/README2.md", raise_for_status=True) as resp:
    #     pass
    # async with client.get("http://localhost:8080/uv.lock") as resp:
    #     # idk exactly how big uv.lock is, but its gotta be big
    #     assert resp.content_length and resp.content_length > 10000
    # If you want to make things slower/experiment with loadgen performance:
    # busy_loop(0.1)
    # await asyncio.sleep(0.1)
