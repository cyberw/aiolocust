import asyncio
import os
import signal
import unittest
from tempfile import TemporaryDirectory

import pytest
from utils import assert_search


async def test_otel_traces_exporter(http_server):  # noqa: ARG001
    with TemporaryDirectory() as tmp_dir:
        script_path = os.path.join(tmp_dir, "my_script.py")

        with open(script_path, "w") as tempfile:
            tempfile.write("""
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from aiolocust.http import request_hook, HttpUser

AioHttpClientInstrumentor().instrument(request_hook=request_hook)

class MyUser(HttpUser):
    async def run(self):
        async with self.client.get("http://localhost:8081/") as resp:
            pass
        async with self.client.get("http://localhost:8081/", name="foo") as resp:
            pass
        print("done!")
""")
        proc = await asyncio.create_subprocess_exec(
            "aiolocust",
            tempfile.name,
            "--duration",
            "2",
            "-u",
            "2",
            env={
                "OTEL_TRACES_EXPORTER": "console",
                **os.environ,
            },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=4)
        except TimeoutError:
            proc.terminate()
            stdout, stderr = await proc.communicate()
            output = stdout.decode(errors="replace")
            print(output)
            pytest.fail("process never terminated")
        else:
            err = stderr.decode(errors="replace")
            print(err)
            assert not err
            output = stdout.decode(errors="replace")
            assert "http://localhost:" in output
            assert "0 (0.0%)" in output
            assert '"trace_id":' in output
            assert '"name": "GET"' in output  # not renamed
            assert '"name": "foo"' in output  # using explicit name
            assert "done!" in output
            assert await proc.wait() == 0


async def test_loglevel(http_server):  # noqa: ARG001
    with TemporaryDirectory() as tmp_dir:
        script_path = os.path.join(tmp_dir, "my_script.py")

        with open(script_path, "w") as tempfile:
            tempfile.write("""
import logging
logger = logging.getLogger(__name__)

async def run(user):
    logger.warning("warning level log message")
    logger.info("info level log message")
    async with user.client.get("http://localhost:8081/") as resp:
        pass
""")
        proc = await asyncio.create_subprocess_exec(
            "aiolocust",
            tempfile.name,
            "--duration",
            "1",
            "--log-level",
            "warning",
            env={
                "OTEL_TRACES_EXPORTER": "console",
                **os.environ,
            },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=4)
        except TimeoutError:
            proc.terminate()
            stdout, stderr = await proc.communicate()
            output = stdout.decode(errors="replace")
            print(output)
            pytest.fail("process never terminated")
        else:
            err = stderr.decode(errors="replace")
            print(err)
            output = stdout.decode(errors="replace")
            assert "warning level log message" in err
            assert "info level log message" not in err
            assert await proc.wait() == 0


@unittest.skipIf(os.name == "nt", reason="Signal handling on windows is hard")
async def test_sigint(http_server):  # noqa: ARG001
    with TemporaryDirectory() as tmp_dir:
        script_path = os.path.join(tmp_dir, "my_script.py")

        with open(script_path, "w") as tempfile:
            tempfile.write("""
async def run(user):
    async with user.client.get("http://localhost:8081/") as resp:
        pass
""")
        proc = await asyncio.create_subprocess_exec(
            "aiolocust",
            tempfile.name,
            "--duration",
            "10",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.sleep(1)
            if os.name == "nt":
                proc.send_signal(signal.CTRL_C_EVENT)
            else:
                proc.send_signal(signal.SIGINT)
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=3)
        except TimeoutError:
            proc.kill()
            stdout, stderr = await proc.communicate()
            output = stdout.decode(errors="replace")
            print(output)
            pytest.fail("process never terminated")
        else:
            output = stdout.decode(errors="replace")
            assert "Summary" in output
            assert await proc.wait() == 0


async def test_unhandled_error_logging(http_server):  # noqa: ARG001
    with TemporaryDirectory() as tmp_dir:
        script_path = os.path.join(tmp_dir, "my_script.py")

        with open(script_path, "w") as tempfile:
            tempfile.write("""
import asyncio

async def run(user):
    await asyncio.sleep(1)
    raise Exception("an error")
""")
        proc = await asyncio.create_subprocess_exec(
            "aiolocust",
            tempfile.name,
            "--duration",
            "1",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=3)
        except TimeoutError:
            proc.kill()
            stdout, stderr = await proc.communicate()
            output = stdout.decode(errors="replace")
            print(output)
            pytest.fail("process never terminated")
        else:
            err = stderr.decode(errors="replace")
            print(err)
            assert "Traceback" in err
            assert 'my_script.py", line 6, in run' in err
            assert 'raise Exception("an error")' in err
            output = stdout.decode(errors="replace")
            print(output)
            assert "Summary" in output
            assert await proc.wait() == 0
            assert_search(r"[12] .* an error", output)
