import asyncio

import pytest
from utils import assert_search

from aiolocust import stats
from aiolocust.runner import LocustClientSession, Runner


@pytest.mark.asyncio
async def test_runner(http_server, capfd):  # noqa: ARG001
    async def run(client: LocustClientSession):
        await asyncio.sleep(1)
        async with client.get("http://localhost:8081/") as resp:
            pass

    r = Runner()
    await r.run_test(run, 1, 5)
    out, err = capfd.readouterr()
    assert err == ""
    print(out)
    # first print will happen after a request has been created, but it is not yet in the window
    assert "http://localhost:8081/ │     0" in out
    # second print should have two requsts in the window
    assert_search(" http://localhost:8081/ │     2|3", out)

    stats.print_table(True)  # call to print summary is made in main, so we do it manually here

    out, err = capfd.readouterr()
    print(out)
    assert err == ""
    assert "Summary" in out
    assert_search(" http://localhost:8081/ │     5|6", out)
    assert "0 (0.0%)" in out
