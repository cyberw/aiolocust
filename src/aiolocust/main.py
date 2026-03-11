import importlib.util
import inspect
import json
import logging
import os
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import typer

from aiolocust import User
from aiolocust.http import HttpUser
from aiolocust.otel import setup_logging
from aiolocust.runner import Runner


class LogLevel(StrEnum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"


app = typer.Typer(add_completion=False)
logger = logging.getLogger(__name__)


def is_user_class(item) -> bool:
    """
    Check if a variable is a runnable (non-abstract) User class
    """
    return bool(inspect.isclass(item)) and issubclass(item, User) and not inspect.isabstract(item)


def load_config(input_string):
    if os.path.isfile(input_string):
        with open(input_string) as f:
            return json.load(f)
    try:
        return json.loads(input_string)
    except json.JSONDecodeError as e:
        print(f"Config is not valid JSON: {e}")
        raise


@app.command()
def main(
    filename: Annotated[str, typer.Argument(help="The test to run")] = "locustfile.py",
    users: Annotated[int, typer.Option("-u", "--users", help="The number of concurrent VUs")] = 1,
    duration: Annotated[int | None, typer.Option("-d", "--duration", help="Stop the test after X seconds")] = None,
    rate: Annotated[
        float | None, typer.Option("-r", "--rate", help="Rate to spawn users at (users per second).")
    ] = None,
    log_level: Annotated[
        LogLevel, typer.Option("--log-level", help="Set the logging level", case_sensitive=False)
    ] = LogLevel.info,
    config: Annotated[dict | None, typer.Option(parser=load_config)] = None,
    event_loops: Annotated[
        int | None,
        typer.Option(
            "--event-loops", help="Set the number of aio event loops", rich_help_panel="Advanced Configuration"
        ),
    ] = None,
):
    log_level_id = getattr(logging, log_level.value.upper())
    setup_logging(log_level_id)
    logger.debug(f"Running with users={users}, duration={duration}, event_loops={event_loops}")

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

    logger.debug(f"config: {config}")
    if user_classes:
        r = Runner(
            [user for user in user_classes.values()],
            user_count=users,
            duration=duration,
            rate=rate,
            config=config,
            event_loops=event_loops,
        )
        r.run_test()
    else:
        typer.echo(f"Error: No User classes or run function defined in {filename}")
