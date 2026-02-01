import asyncio

from utils import assert_search

from aiolocust.runner import LocustClientSession, Runner


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
    # second print should have two requsts in the window, but Windows on GH is randomly slow
    assert_search(" http://localhost:8081/ │     1|2|3", out)

    # Summary not yet implemented for OTEL
    # # call to print summary is normally made in main, so we have to do it manually here
    # r.stats.print_table(True)

    # out, err = capfd.readouterr()
    # print(out)
    # assert err == ""
    # assert "Summary" in out
    # assert_search(" http://localhost:8081/ │     4|5|6", out)
    # assert "0 (0.0%)" in out
