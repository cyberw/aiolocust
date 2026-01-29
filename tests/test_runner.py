import asyncio

from utils import assert_search

from aiolocust.runner import LocustClientSession, Runner


async def test_runner(http_server, capfd):  # noqa: ARG001
    async def run(client: LocustClientSession):
        await asyncio.sleep(1)
        async with client.get("http://localhost:8081/") as resp:
            pass

    r = Runner()
    await r.run_test(run, 1, 4)
    out, err = capfd.readouterr()
    assert err == ""
    print(out)
    # first print will happen after a request has been created, but it is not yet in the window
    assert "http://localhost:8081/ │     0" in out
    # second print should have two requsts in the window, but Windows on GH is randomly slow
    assert_search(" http://localhost:8081/ │     1|2|3", out)

    # call to print summary is normally made in main, so we have to do it manually here
    r.stats.print_table(True)

    out, err = capfd.readouterr()
    print(out)
    assert err == ""
    assert "Summary" in out
    assert_search(" http://localhost:8081/ │     4|5", out)
    assert "0 (0.0%)" in out
