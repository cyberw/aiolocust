# If you want to vary load over time, you can specify stages in the config.
# For example, this will ramp up with one user/second and then ramp down with two users/second:
# aiolocust --config '{ "stages": [{"duration": 10, "target": 10}, {"duration": 5, "target": 0}] }'

import asyncio

from aiolocust import HttpUser, Runner


class MyUser(HttpUser):
    async def run(self):
        async with self.client.get("http://localhost:8080/") as resp:
            pass
        async with self.client.get("http://localhost:8080/") as resp:
            assert "Example" in await resp.text()
        await asyncio.sleep(0.1)


if __name__ == "__main__":
    # you can specify config via the Runner directly too:
    Runner(
        [MyUser],
        config={
            "stages": [
                {"duration": 10, "target": 10},
                {"duration": 5, "target": 0},
            ]
        },
    ).run_test()
