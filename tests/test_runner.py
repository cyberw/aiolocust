import asyncio
import os

import pytest
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from utils import assert_search

from aiolocust import otel
from aiolocust.http import LocustClientSession, request_hook
from aiolocust.runner import Runner


async def test_runner(http_server, capteesys):  # noqa: ARG001
    async def run(client: LocustClientSession):
        await asyncio.sleep(1)
        async with client.get("http://localhost:8081/") as resp:
            pass
        async with client.get("http://localhost:8081/404") as resp:
            pass
        async with client.get("http://localhost:8081/", name="renamed") as resp:
            resp.error = "Oh no"
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
    assert_search(r" renamed[ ]+│[ ]+[234] .* \(100.0%\)", out)
    assert "Error" in out
    assert_search(r"[234] .* assert 'foo' in 'OK'", out)
    assert_search(r"[234] .* 404,", out)
    assert_search(r"[234] .* Oh no", out)
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


@pytest.mark.skipif(
    condition=not bool(os.environ.get("VSCODE_CLI")), reason="Only works when run individually, not sure why"
)
async def test_runner_w_instrumentation(http_server, capfd):  # noqa: ARG001
    AioHttpClientInstrumentor().instrument(request_hook=request_hook)
    os.environ["OTEL_TRACES_EXPORTER"] = "console"
    otel.setup_trace_exporters()

    async def run(client: LocustClientSession):
        await asyncio.sleep(1)
        async with client.get("http://localhost:8081/", name="foo") as resp:
            pass
        async with client.get("http://localhost:8081/404", name="foo") as resp:
            pass

    r = Runner()
    await r.run_test(run, 1, 2)
    out, err = capfd.readouterr()
    assert err == ""
    assert '"trace_id"' in out
    assert '"name": "foo"' in out
    assert '"name": "GET"' not in out
    assert "Summary" in out
    assert_search(r" foo[ ]+│[ ]+[24] .* \(50.0%\)", out)
    assert "Error" in out
    assert_search(r"[12] .* 404,", out)
    assert "bar" not in out
