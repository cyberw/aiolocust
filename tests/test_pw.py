# trust me, this works, but it needs playwright to be installed and a browser to be downloaded


# from aiolocust.pw import PlaywrightUser
# from aiolocust.runner import Runner
# from tests.test_runner import WINDOWS_DELAY
# from tests.utils import assert_search


# async def test_runner(http_server, capteesys):  # noqa: ARG001
#     class TestUser(PlaywrightUser):
#         async def run(self):
#             await self.page.goto("https://www.microsoft.com/")
#             await self.page.click("#uhfLogo > img", timeout=10000)
#             await self.page.click("this_doesnt_exist", timeout=10)

#     r = Runner([TestUser])
#     await r.run_test(1, 4 + WINDOWS_DELAY)
#     out, err = capteesys.readouterr()
#     assert err == ""
#     assert "Summary" in out
#     assert_search(r" https://www.microsoft.com/[ ]+│[ ]+[12] .* \(0.0%\)", out)

#     assert_search(r" #uhfLogo > img[ ]+│[ ]+[12] .* \(0.0%\)", out)
#     assert "Error" in out
#     assert_search(r"[12] .* Page.click: Timeout", out)
#     assert_search(r'waiting for locator\("this_doesnt_exist"\)', out)
#     assert "bar" not in out
