import asyncio
import json
import os
import signal
import unittest
from tempfile import TemporaryDirectory

from utils import assert_search


@unittest.skipIf(os.name == "nt", reason="otel instrumentation seems to have some issues with freethreading on Windows")
async def test_otel_autoinstrumentation(http_server):  # noqa: ARG001
    with TemporaryDirectory() as tmp_dir:
        script_path = os.path.join(tmp_dir, "my_script.py")

        with open(script_path, "w") as tempfile:
            tempfile.write("""
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from aiolocust.users.http import request_hook, HttpUser

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
            "-u",
            "20",
            "--iterations",
            "30",
            env={
                "OTEL_TRACES_EXPORTER": "console",
                **os.environ,
            },
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=0.1)
        except TimeoutError:
            proc.terminate()
            stdout, stderr = await proc.communicate()
            err = stdout.decode(errors="replace")
            print(err)
            output = stdout.decode(errors="replace")
            print(output)
            raise AssertionError("process never terminated") from None
        else:
            err = stderr.decode(errors="replace")
            print(err)
            output = stdout.decode(errors="replace")
            print(output)
            assert "http://localhost:" in output
            assert " foo                    │    30 │ 0 (0.0%)" in output
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
            "--iterations",
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
            raise AssertionError("process never terminated") from None
        else:
            err = stderr.decode(errors="replace")
            print(err)
            output = stdout.decode(errors="replace")
            assert "warning level log message" in err
            assert "info level log message" not in err
            assert "Exception" not in err
            assert await proc.wait() == 0


async def test_host_param(http_server):  # noqa: ARG001
    with TemporaryDirectory() as tmp_dir:
        script_path = os.path.join(tmp_dir, "my_script.py")

        with open(script_path, "w") as tempfile:
            tempfile.write("""
async def run(user):
    async with user.client.get("/?foo") as resp:
        pass
""")
        proc = await asyncio.create_subprocess_exec(
            "aiolocust",
            tempfile.name,
            "--iterations",
            "1",
            "--host",
            "http://localhost:8081",
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
            raise AssertionError("process never terminated") from None
        else:
            err = stderr.decode(errors="replace")
            output = stdout.decode(errors="replace")
            print(output)
            print(err)
            assert " http://localhost:8081/?foo │     1 │ 0 (0.0%) │" in output
            assert "Error" not in output
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
            raise AssertionError("process never terminated") from None
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
            raise AssertionError("process never terminated") from None
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


async def test_config_and_stages(http_server):  # noqa: ARG001
    with TemporaryDirectory() as tmp_dir:
        with open(os.path.join(tmp_dir, "my_script.py"), "w") as tempfile:
            tempfile.write("""
import asyncio

async def run(user):
    async with user.client.get("http://localhost:8081/") as resp:
        pass
    if user.running:
        await asyncio.sleep(1)
""")
        with open(os.path.join(tmp_dir, "my_config.json"), "w") as configfile:
            json.dump(
                {
                    "stages": [{"duration": 3, "target": 1}, {"duration": 1, "target": 20}],
                },
                configfile,
            )

        proc = await asyncio.create_subprocess_exec(
            "aiolocust",
            tempfile.name,
            "--config",
            configfile.name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=6)
        except TimeoutError:
            proc.kill()
            stdout, stderr = await proc.communicate()
            output = stdout.decode(errors="replace")
            print(output)
            raise AssertionError("process never terminated") from None
        else:
            err = stderr.decode(errors="replace")
            print(err)
            output = stdout.decode(errors="replace")
            print(output)
            assert "Summary" in output
            assert await proc.wait() == 0
            assert_search(r"0\.[0-9]*/s", output)  # first one
            assert_search(r"[2-9]\.[0-9]*/s", output)  # last one


async def test_user_forwards_params_to_session_and_handles_timeouts(http_server):  # noqa: ARG001
    proc = await asyncio.create_subprocess_exec(
        "aiolocust",
        "examples/advanced_user_class_settings.py",
        "--iterations",
        "3",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=6)
    except TimeoutError:
        proc.kill()
        stdout, stderr = await proc.communicate()
        output = stdout.decode(errors="replace")
        print(output)
        raise AssertionError("process never terminated") from None
    else:
        err = stderr.decode(errors="replace")
        print(err)
        assert not err
        output = stdout.decode(errors="replace")
        print(output)
        assert "Summary" in output
        assert await proc.wait() == 0
        assert_search(r"3 .* TimeoutError", output)
