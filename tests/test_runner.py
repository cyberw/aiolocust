import asyncio

from utils import assert_search

from aiolocust.runner import LocustClientSession, Runner


async def test_runner(http_server, capteesys):  # noqa: ARG001
    async def run(client: LocustClientSession):
        await asyncio.sleep(1)
        async with client.get("http://localhost:8081/") as resp:
            pass
        async with client.get("http://localhost:8081/404") as resp:
            pass
        async with client.get("http://localhost:8081/") as resp:
            assert "foo" in await resp.text()
        async with client.get("http://localhost:8081/") as resp:
            assert "bar" in await resp.text()

    r = Runner()
    await r.run_test(run, 1, 3)
    out, err = capteesys.readouterr()
    assert err == ""
    assert "Summary" in out
    assert_search(r" http://localhost:8081/[ ]+│[ ]+[468] .* \(50.0%\)", out)
    assert "Error" in out
    assert_search(r"[234] .* assert 'foo' in 'OK'", out)
    assert_search(r"[234] .* 404,", out)
    assert "bar" not in out


async def test_runner_w_otel(http_server, capteesys):  # noqa: ARG001
    async def run(client: LocustClientSession):
        await asyncio.sleep(1)
        async with client.get("http://localhost:8081/") as resp:
            pass
        async with client.get("http://localhost:8081/404") as resp:
            pass
        async with client.get("http://localhost:8081/") as resp:
            assert "foo" in await resp.text()
        async with client.get("http://localhost:8081/") as resp:
            assert "bar" in await resp.text()

    r = Runner()
    await r.run_test(run, 1, 3)
    out, err = capteesys.readouterr()
    assert err == ""
    assert "Summary" in out
    assert_search(r" http://localhost:8081/[ ]+│[ ]+[468] .* \(50.0%\)", out)
    assert "Error" in out
    assert_search(r"[234] .* assert 'foo' in 'OK'", out)
    assert_search(r"[234] .* 404,", out)
    assert "bar" not in out
