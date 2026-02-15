# A slightly more advanced example
import asyncio

from aiolocust import LocustClientSession, Runner


async def run(client: LocustClientSession):
    # ensure some specific content in response
    async with client.get("http://localhost:8080/") as resp:
        text = await resp.text()
        assert text.startswith("Example"), "Response did not start with 'Example'"

    # rename request, use alternate way to log an error without interrupting user flow
    async with client.get("http://localhost:8080/") as resp:
        text = await resp.text()
        if not text.startswith("foo"):
            resp.error = "Response did not start with 'foo'"

    # interrupt the user flow on http status code error
    async with client.get("http://localhost:8080/", raise_for_status=True) as resp:
        pass

    # slow down a little
    await asyncio.sleep(0.1)

    # If you want to intentionally mess with loadgen performance to prove freethreading works:
    # def busy_loop(seconds: float):
    #     end = time.perf_counter() + seconds
    #     while time.perf_counter() < end:
    #         pass
    # busy_loop(0.1)


# make this file runnable with "python locustfile.py"
if __name__ == "__main__":
    asyncio.run(Runner().run_test(run, 1, 1))
