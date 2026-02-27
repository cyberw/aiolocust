import asyncio
import importlib.util
import inspect
import sys
from pathlib import Path
from typing import Annotated

import typer

from aiolocust import User
from aiolocust.http import HttpUser
from aiolocust.runner import Runner

app = typer.Typer(add_completion=False)


def is_user_class(item) -> bool:
    """
    Check if a variable is a runnable (non-abstract) User class
    """
    return bool(inspect.isclass(item)) and issubclass(item, User) and not inspect.isabstract(item)


@app.command()
def main(
    filename: Annotated[str, typer.Argument(help="The test to run")] = "locustfile.py",
    users: Annotated[int, typer.Option("-u", "--users", help="The number of concurrent VUs")] = 1,
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

    # Return our two-tuple
    user_classes = {name: value for name, value in vars(module).items() if is_user_class(value)}
    if not user_classes and hasattr(module, "run"):

        class SimpleUser(HttpUser):
            async def run(self):
                pass  # This will be overwritten immediately, but needs to be here to satisfy the abstract base class requirement

        SimpleUser.run = module.run
        user_classes = {"SimpleUser": SimpleUser}
    if user_classes:
        r = Runner([user for user in user_classes.values()])
        asyncio.run(r.run_test(users, duration, event_loops))
    else:
        typer.echo(f"Error: No User classes or run function defined in {filename}")
