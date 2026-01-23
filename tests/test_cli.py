from click.testing import CliRunner

from aiolocust.cli import cli


def test_cli_run():
    # don't forget to start nginx first
    runner = CliRunner()
    with runner.isolated_filesystem():
        with open("my_locustfile.py", "w") as f:
            f.write("""
async def run(client: LocustClientSession):
    async with client.get("http://localhost:8080/") as resp:
        pass
""")

        result = runner.invoke(cli, ["my_locustfile.py", "--run-time", "1"])
        assert result.exit_code == 0
        assert "http://localhost:" in result.output
        assert "0 (0.0%)" in result.output
