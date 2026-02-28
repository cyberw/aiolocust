#!/usr/bin/env aiolocust
# The above line, in combination with marking the file as executable (chmod +x),
# makes it runnable (on unix-like systems) using just: ./advanced.py
# You can still pass regular parameters like --duration etc

import asyncio

from aiolocust import Runner
from aiolocust.http import HttpUser


class MyUser(HttpUser):
    async def run(self):
        # ensure some specific content in response
        async with self.client.get("http://localhost:8080/") as resp:
            text = await resp.text()
            assert text.startswith("Example"), "Response did not start with 'Example'"

        # rename request, use alternate way to log an error without interrupting user flow
        async with self.client.get("http://localhost:8080/") as resp:
            text = await resp.text()
            if not text.startswith("foo"):
                resp.error = "Response did not start with 'foo'"

        # interrupt the user flow on http status code error
        async with self.client.get("http://localhost:8080/", raise_for_status=True) as resp:
            pass

        # If you want to intentionally mess with loadgen performance to prove freethreading works:
        # def busy_loop(seconds: float):
        #     end = time.perf_counter() + seconds
        #     while time.perf_counter() < end:
        #         pass
        # busy_loop(0.1)


# make this file runnable with "python advanced.py"
if __name__ == "__main__":
    asyncio.run(Runner([MyUser]).run_test(1, 1))
