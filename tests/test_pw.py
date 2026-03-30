import pytest
from utils import assert_search

from aiolocust.runner import Runner

try:
    from aiolocust.pw import PlaywrightUser
except ImportError:
    PlaywrightUser = object


@pytest.mark.skipif(condition=PlaywrightUser is object, reason="Playwright is not installed")
def test_runner(http_server, capteesys):  # noqa: ARG001
    class TestUser(PlaywrightUser):  # pyright: ignore[reportGeneralTypeIssues]
        async def run(self):
            await self.page.goto("https://www.microsoft.com/")
            await self.page.click("#uhfLogo > img", timeout=10000)
            await self.page.click("this_doesnt_exist", timeout=10)

    Runner([TestUser], 5, iterations=5).run_test()
    out, err = capteesys.readouterr()
    assert err == ""
    assert "Summary" in out
    assert_search(r" https://www.microsoft.com/[ ]+│[ ]+[5] .* \(0.0%\)", out)

    assert_search(r" #uhfLogo > img[ ]+│[ ]+[5] .* \(0.0%\)", out)
    assert "Error" in out
    assert_search(r"[5] .* Page.click: Timeout", out)
    assert_search(r'waiting for locator\("this_doesnt_exist"\)', out)
    assert "bar" not in out
