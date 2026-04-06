import aiohttp

from aiolocust import HttpUser


class TimeoutUser(HttpUser):
    # any extra aiohttp.ClientSession args you want to pass
    session_kwargs = {"timeout": aiohttp.ClientTimeout(0.0001)}

    async def run(self):
        async with self.client.get("http://localhost:8080/") as resp:
            pass
