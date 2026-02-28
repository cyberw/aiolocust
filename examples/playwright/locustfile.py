# Note: PlaywrightUser requires Playwright to be installed.
# This is a PoC and you're likely to encounter some issues/limitations.

# combine it with --event-loops 1
# running multiple loops using uvloop causes errors, and there's not much point anyway
from aiolocust.pw import PlaywrightUser


class MyUser(PlaywrightUser):
    async def run(self):
        await self.page.goto("https://www.microsoft.com/")
        await self.page.click("#uhfLogo > img", timeout=10000)
        await self.page.click("this_doesnt_exist", timeout=10)
