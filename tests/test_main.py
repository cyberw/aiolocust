import os

from typer.testing import CliRunner

from aiolocust.main import app


def _timeout_handler(_signum, _frame):
    if bool(os.environ.get("VSCODE_CLI")):
        pass  # disable timeout when debugging
    else:
        raise TimeoutError("test timed out after 10 seconds")


def test_main(http_server):  # noqa: ARG001
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
        result = runner.invoke(app, ["my_locustfile.py", "--iterations", "3", "-u", "2"])
        assert "http://localhost:" in result.output
        assert "0 (0.0%)" in result.output
        assert result.exit_code == 0


def test_run_method(http_server):  # noqa: ARG001
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("my_locustfile.py", "w") as f:
            f.write("""
async def run(user):
    async with user.client.get("http://localhost:8081/") as resp:
        pass
""")
        result = runner.invoke(app, ["my_locustfile.py", "--iterations", "3", "-u", "2"])
        assert "http://localhost:" in result.output
        assert "0 (0.0%)" in result.output
        assert result.exit_code == 0


def test_on_start():  # noqa: ARG001
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("my_locustfile.py", "w") as f:
            f.write("""
from aiolocust import HttpUser
foo = None

async def on_start():
    global foo
    foo = "bar"

class MyUser(HttpUser):
    async def run(self):
        print(foo)
""")
        result = runner.invoke(app, ["my_locustfile.py", "--iterations", "1"])
        assert "bar" in result.output
        assert result.exit_code == 0


def test_html_report(http_server):  # noqa: ARG001
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("my_locustfile.py", "w") as f:
            f.write("""
async def run(user):
    async with user.client.get("http://localhost:8081/") as resp:
        pass
""")
        result = runner.invoke(
            app,
            ["my_locustfile.py", "--iterations", "3", "-u", "2", "--html-report", "reports/report.html"],
        )
        print(result.output)
        assert "http://localhost:" in result.output
        assert "0 (0.0%)" in result.output
        assert result.exit_code == 0
        assert result.output.count("http://localhost:") == 1  # no accidental duplicate print
        with open("reports/report.html") as report:
            html = report.read()
        assert "<!DOCTYPE html>" in html
        assert "http://localhost:" in html
        assert "target user count: 2" in html
        assert "Total" in html


def test_relative_import_in_module():
    runner = CliRunner()
    with runner.isolated_filesystem():
        os.makedirs("mytests")
        with open("mytests/__init__.py", "w") as f:
            f.write("")
        with open("mytests/helper.py", "w") as f:
            f.write(
                """
async def run(user):
    pass
"""
            )
        with open("mytests/my_locustfile.py", "w") as f:
            f.write(
                """
from .helper import run
"""
            )

        result = runner.invoke(app, ["mytests/my_locustfile.py", "--iterations", "1"])
        assert result.exit_code == 0


def test_config(http_server):  # noqa: ARG001
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("my_locustfile.py", "w") as f:
            f.write("""
async def run(user):
    async with user.client.get("http://localhost:8081/") as resp:
        pass
""")
        result = runner.invoke(
            app,
            [
                "my_locustfile.py",
                "--config",
                '{ "stages": [{ "duration": 2, "target": 2 }] }',
            ],
        )
        assert "http://localhost:" in result.output
        assert "0 (0.0%)" in result.output
        assert result.exit_code == 0
