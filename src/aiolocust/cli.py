import asyncio
import importlib.util
import sys
from pathlib import Path

import click

from aiolocust.runner import main


@click.command()
@click.argument("filename", type=click.Path(exists=True), default="locustfile.py")
@click.option("-u", "--users", type=int, default=1)
@click.option("-t", "--run-time", type=click.INT, default=None)
@click.option("--event-loops", type=click.INT, default=None)
def cli(filename, users, run_time, event_loops):
    file_path = Path(filename).resolve()
    module_name = file_path.stem

    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        click.echo(f"Error: Could not load the file at {file_path}")
        return

    module = importlib.util.module_from_spec(spec)

    # Add the module to sys.modules so it behaves like a normal import
    sys.modules[module_name] = module

    # Run any top-level code
    spec.loader.exec_module(module)

    if hasattr(module, "run"):
        asyncio.run(main(module.run, users, run_time, event_loops))
    else:
        click.echo(f"Error: No run function defined in {filename}")


if __name__ == "__main__":
    cli()
