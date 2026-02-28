# Note: PlaywrightUser requires Playwright to be installed.
# This is a PoC and you're likely to encounter some issues/limitations.
import asyncio

from aiolocust.pw import PlaywrightUser
from aiolocust.runner import Runner


class MyUser(PlaywrightUser):
    async def run(self):
        await self.client.goto("https://www.microsoft.com/")
        await self.client.click("#uhfLogo > img", timeout=10000)
        await self.client.click("this_doesnt_exist", timeout=10)


# make this file runnable with "python advanced.py"
if __name__ == "__main__":
    asyncio.run(Runner([MyUser]).run_test(1, 1))
