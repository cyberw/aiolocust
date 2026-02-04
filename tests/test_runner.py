import asyncio

from utils import assert_search

from aiolocust.runner import LocustClientSession, Runner


async def test_runner(http_server, capfd):  # noqa: ARG001
    async def run(client: LocustClientSession):
        await asyncio.sleep(1)
        async with client.get("http://localhost:8081/") as resp:
            pass
        async with client.get("http://localhost:8081/") as resp:
            assert "foo" in await resp.text()

    r = Runner()
    await r.run_test(run, 1, 3)
    out, err = capfd.readouterr()
    assert err == ""
    print(out)
    assert "Summary" in out
    assert_search(r" http://localhost:8081/ │[ ]+[468] .* \(50.0%\)", out)
    assert_search(r"Errors", out)
    assert_search(r"assert 'foo' in 'OK' .* [234]", out)
