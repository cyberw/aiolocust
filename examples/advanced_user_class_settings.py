import aiohttp

from aiolocust.http import HttpUser


class TimeoutUser(HttpUser):
    # HttpUser forwards any extra keyword parameters to its underlying aiohttp.ClientSession
    # See https://docs.aiohttp.org/en/stable/client_reference.html#client-session
    def __init__(self, *args):
        super().__init__(*args, timeout=aiohttp.ClientTimeout(0.0001))

    async def run(self):
        async with self.client.get("http://localhost:8080/") as resp:
            pass
