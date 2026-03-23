import asyncio
import os

import aiohttp
import pytest
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from utils import assert_search

from aiolocust import otel
from aiolocust.http import HttpUser, LocustClientSession, request_hook
from aiolocust.runner import Runner, Stage, desired_user_count

WINDOWS_DELAY = 1 if os.name == "nt" else 0


def test_basic(http_server, capteesys):  # noqa: ARG001
    class TestUser(HttpUser):
        async def run(self):
            await asyncio.sleep(1)
            async with self.client.get("http://localhost:8081/") as resp:
                pass
            async with self.client.get("http://localhost:8081/404") as resp:
                pass
            async with self.client.get("http://localhost:8081/", name="renamed") as resp:
                resp.error = "Oh no"
            async with self.client.get("http://localhost:8081/") as resp:
                assert "foo" in await resp.text()
            async with self.client.get("http://localhost:8081/") as resp:
                assert "bar" in await resp.text()

    Runner([TestUser], 1, 3 + WINDOWS_DELAY).run_test()
    out, err = capteesys.readouterr()
    assert err == ""
    assert "Summary" in out
    assert_search(r" http://localhost:8081/[ ]+│[ ]+[46] .* \(50.0%\)", out)
    assert_search(r" renamed[ ]+│[ ]+[23] .* \(100.0%\)", out)
    assert "Error" in out
    assert_search(r"[23] .* assert 'foo' in 'OK'", out)
    assert_search(r"[23] .* 404,", out)
    assert_search(r"[23] .* Oh no", out)
    assert "bar" not in out


def test_unhandled_exception(http_server, capteesys):  # noqa: ARG001
    class TestUser(HttpUser):
        async def run(self):
            await asyncio.sleep(1)
            raise Exception("an error")

    Runner([TestUser], 1, 1).run_test()
    out, err = capteesys.readouterr()
    assert err == ""
    assert "Summary" in out
    assert_search(r"[12] .* an error", out)


from contextlib import asynccontextmanager


def test_timeout_catching(http_server, capteesys):  # noqa: ARG001
    class TestUser(HttpUser):
        @asynccontextmanager
        async def cm(self):
            async with LocustClientSession(
                self.runner, self.base_url, timeout=aiohttp.ClientTimeout(0.0001)
            ) as self.client:
                yield

        async def run(self):
            await asyncio.sleep(0.2)
            async with self.client.get("http://localhost:8081/") as resp:
                pass
            raise Exception("We'll never get here")

    Runner([TestUser], 1, 1).run_test()
    out, err = capteesys.readouterr()
    assert err == ""
    assert "Summary" in out
    assert "(100.0%)" in out
    assert not "We'll never get here" in out
    assert_search(r"\d .* TimeoutError", out)


def test_w_otel(http_server, capteesys):  # noqa: ARG001
    class TestUser(HttpUser):
        async def run(self):
            await asyncio.sleep(1)
            async with self.client.get("http://localhost:8081/") as resp:
                pass
            async with self.client.get("http://localhost:8081/404") as resp:
                pass
            async with self.client.get("http://localhost:8081/") as resp:
                assert "foo" in await resp.text()
            async with self.client.get("http://localhost:8081/") as resp:
                assert "bar" in await resp.text()

    Runner([TestUser], 1, 3 + WINDOWS_DELAY).run_test()
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
def test_w_instrumentation(http_server, capfd):  # noqa: ARG001
    AioHttpClientInstrumentor().instrument(request_hook=request_hook)
    os.environ["OTEL_TRACES_EXPORTER"] = "console"
    otel.setup_trace_exporters()

    class TestUser(HttpUser):
        async def run(self):
            await asyncio.sleep(1)
            async with self.client.get("http://localhost:8081/", name="foo") as resp:
                pass
            async with self.client.get("http://localhost:8081/404", name="foo") as resp:
                pass

    Runner([TestUser], 1, 2).run_test()
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


def test_manual_shutdown(http_server, capteesys):  # noqa: ARG001
    class TestUser(HttpUser):
        async def run(self):
            async with self.client.get("http://localhost:8081/") as resp:
                pass
            self.runner.shutdown()  # manually trigger shutdown from user code

    Runner([TestUser], duration=1).run_test()
    out, err = capteesys.readouterr()
    assert err == ""
    print(out)
    assert "Summary" in out
    assert " http://localhost:8081/ │     1 │ 0 (0.0%) " in out


def test_iterations(http_server, capteesys):  # noqa: ARG001
    class TestUser(HttpUser):
        async def run(self):
            async with self.client.get("http://localhost:8081/") as resp:
                pass
            async with self.client.get("http://localhost:8081/") as resp:
                assert "foo" in await resp.text()

    Runner(
        [TestUser],
        user_count=2,
        iterations=30,
        event_loops=1,
        duration=2,  # ensure we dont run forever, even if the iteration limit fails
    ).run_test()
    out, err = capteesys.readouterr()
    assert err == ""
    print(out)
    assert "Summary" in out
    assert_search(r" http://localhost:8081/.* 60 .* 30 \(50.0%\)", out)
    assert "Error" in out
    assert_search(r"30 .* assert 'foo' in 'OK'", out)


def test_desired_user_count():
    stages = [
        Stage(duration=2, target=2),
        Stage(duration=2, target=2),
        Stage(duration=2, target=4),
        Stage(duration=2, target=0),
        Stage(duration=2, target=10),
    ]
    assert desired_user_count(stages, 0) == 0
    assert desired_user_count(stages, 0.1) == 1  # using math.ceil to avoid 0 users at the start of the test
    assert desired_user_count(stages, 2) == 2
    assert desired_user_count(stages, 3) == 2  # no change in second stage
    assert desired_user_count(stages, 4) == 2
    assert desired_user_count(stages, 5) == 3  # halfway through third stage
    assert desired_user_count(stages, 6) == 4
    assert desired_user_count(stages, 7) == 2  # halfway through ramp down stage
    assert desired_user_count(stages, 8) == 0  # end of ramp down stage
    assert desired_user_count(stages, 9) == 5  # can ramp up again after ramping down to 0
    assert desired_user_count(stages, 9.3) == 7  # floats are nice
    assert desired_user_count(stages, 10) == 10
    assert desired_user_count(stages, 999) is None
    assert desired_user_count([Stage(0, 100), Stage(1, 100)], 0.001) == 100  # correctly handles instant ramp up
