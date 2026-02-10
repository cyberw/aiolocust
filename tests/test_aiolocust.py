import asyncio
import os
from tempfile import TemporaryDirectory

import pytest


async def test_otel_traces_exporter(http_server):  # noqa: ARG001
    with TemporaryDirectory() as tmp_dir:
        script_path = os.path.join(tmp_dir, "my_script.py")

        with open(script_path, "w") as tempfile:
            tempfile.write("""
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
AioHttpClientInstrumentor().instrument()

async def run(client):
    async with client.get("http://localhost:8081/", ) as resp:
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
            assert "done!" in output
            assert await proc.wait() == 0
