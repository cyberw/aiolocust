import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import Annotated

import typer

from aiolocust.runner import Runner

app = typer.Typer(add_completion=False)


@app.command()
def main(
    filename: Annotated[str, typer.Argument(help="The test to run")] = "locustfile.py",
    users: Annotated[int, typer.Option("-u", "--users", help="The number of concurrent VUs")] = 1,
    spawn_rate: Annotated[
        int | None, typer.Option("-r", "--spawn-rate", help="Rate to spawn users at (users per second).")
    ] = None,
    duration: Annotated[int | None, typer.Option("-d", "--duration", help="Stop the test after X seconds")] = None,
    event_loops: Annotated[
        int | None,
        typer.Option(
            "--event-loops", help="Set the number of aio event loops", rich_help_panel="Advanced Configuration"
        ),
    ] = None,
):
    file_path = Path(filename).resolve()
    if not file_path.exists():
        typer.echo(f"Error: Could not find the file at {file_path}")
        raise typer.Exit(code=1)

    module_name = file_path.stem

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        typer.echo(f"Error: Could not load the file at {file_path}")
        raise typer.Exit(code=1)

    module = importlib.util.module_from_spec(spec)

    # Add the module to sys.modules so it behaves like a normal import
    sys.modules[module_name] = module

    # Run any top-level code
    spec.loader.exec_module(module)

    if hasattr(module, "run"):
        r = Runner()
        asyncio.run(r.run_test(module.run, users, spawn_rate, duration, event_loops))
    else:
        typer.echo(f"Error: No run function defined in {filename}")
