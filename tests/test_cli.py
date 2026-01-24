import signal

from click.testing import CliRunner

from aiolocust.cli import cli


def _timeout_handler(_signum, _frame):
    raise TimeoutError("test timed out after 10 seconds")


def test_cli(http_server):  # noqa: ARG001
    # ensure long-running hangs fail quickly in CI/local runs
    signal.signal(signal.SIGALRM, _timeout_handler)
    signal.alarm(10)
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("my_locustfile.py", "w") as f:
            f.write("""
async def run(client: LocustClientSession):
    async with client.get("http://localhost:8081/") as resp:
        pass
""")

        result = runner.invoke(cli, ["my_locustfile.py", "--run-time", "1"])
        assert result.exit_code == 0
        assert "http://localhost:" in result.output
        assert "0 (0.0%)" in result.output
    # clear the alarm whether the test passed or failed
    signal.alarm(0)
