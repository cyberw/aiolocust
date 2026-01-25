import asyncio

import pytest

from aiolocust.runner import LocustClientSession, run_test


@pytest.mark.asyncio
async def test_runner(http_server, capfd):  # noqa: ARG001
    async def run(client: LocustClientSession):
        await asyncio.sleep(1)
        print("hello")
        async with client.get("http://localhost:8081/") as resp:
            pass

    await run_test(run, 1, 2)
    out, err = capfd.readouterr()
    assert err == ""
    assert " http://localhost:8081/ " in out
    assert "0 (0.0%)" in out
