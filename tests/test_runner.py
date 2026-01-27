import asyncio

import pytest

from aiolocust import stats
from aiolocust.runner import LocustClientSession, run_test


@pytest.mark.asyncio
async def test_runner(http_server, capfd):  # noqa: ARG001
    async def run(client: LocustClientSession):
        await asyncio.sleep(0.9)
        async with client.get("http://localhost:8081/") as resp:
            pass

    await run_test(run, 1, 5)
    out, err = capfd.readouterr()
    assert err == ""
    print(out)
    # first print will happen after a request has been created, but it is not yet in the window
    assert "http://localhost:8081/ │     0" in out
    # second print should have two requsts in the window
    assert "http://localhost:8081/ │     2" in out

    stats.print_table(True)  # call to print summary is made in main, so we do it manually here

    out, err = capfd.readouterr()
    print(out)
    assert err == ""
    assert "Summary" in out
    assert " http://localhost:8081/ │     5" in out or " http://localhost:8081/ │     6" in out
    assert "0 (0.0%)" in out
