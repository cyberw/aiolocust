import asyncio
import importlib.util
import sys
from pathlib import Path
from typing import Annotated

import typer

from aiolocust.runner import main

app = typer.Typer()


@app.command()
def cli(
    filename: Annotated[str, typer.Argument()] = "locustfile.py",
    users: int = 1,
    run_time: int | None = None,
    event_loops: int | None = None,
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
        asyncio.run(main(module.run, users, run_time, event_loops))
    else:
        typer.echo(f"Error: No run function defined in {filename}")
