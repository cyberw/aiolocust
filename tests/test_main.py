import signal

from typer.testing import CliRunner

from aiolocust.main import app


def _timeout_handler(_signum, _frame):
    raise TimeoutError("test timed out after 10 seconds")


def test_main(http_server):  # noqa: ARG001
    # SIGALRM isn't available on Windows; only set an alarm when present
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(10)
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("my_locustfile.py", "w") as f:
            f.write("""
from aiolocust import HttpUser

class MyUser(HttpUser):
    async def run(self):
        async with self.client.get("http://localhost:8081/") as resp:
            pass
""")
        result = runner.invoke(app, ["my_locustfile.py", "--duration", "3", "-u", "2"])
        assert "http://localhost:" in result.output
        assert "0 (0.0%)" in result.output
        assert result.exit_code == 0

    if hasattr(signal, "SIGALRM"):
        signal.alarm(0)


def test_run_method(http_server):  # noqa: ARG001
    # SIGALRM isn't available on Windows; only set an alarm when present
    if hasattr(signal, "SIGALRM"):
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(10)
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("my_locustfile.py", "w") as f:
            f.write("""
async def run(user):
    async with user.client.get("http://localhost:8081/") as resp:
        pass
""")
        result = runner.invoke(app, ["my_locustfile.py", "--duration", "3", "-u", "2"])
        assert "http://localhost:" in result.output
        assert "0 (0.0%)" in result.output
        assert result.exit_code == 0

    if hasattr(signal, "SIGALRM"):
        signal.alarm(0)
