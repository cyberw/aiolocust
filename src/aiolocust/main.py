import importlib.util
import inspect
import json
import logging
import os
import sys
from enum import StrEnum
from pathlib import Path
from typing import Annotated

import click
import typer

from aiolocust import User
from aiolocust.otel import setup_logging
from aiolocust.runner import Runner
from aiolocust.users.http import HttpUser


class LogLevel(StrEnum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"


app = typer.Typer(add_completion=False)
logger = logging.getLogger(__name__)
# avoid annoying "Using selector: KqueueSelector" when running in debug:
logging.getLogger("asyncio").setLevel(logging.INFO)


def is_user_class(item) -> bool:
    """
    Check if a variable is a runnable (non-abstract) User class
    """
    return bool(inspect.isclass(item)) and issubclass(item, User) and not inspect.isabstract(item)


def load_config(input_string):
    if os.path.isfile(input_string):
        try:
            with open(input_string) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"Config file is not valid JSON: {e}")
            raise
        except Exception as e:
            print(f"Could not load file: {e}")
            raise
    try:
        return json.loads(input_string)
    except json.JSONDecodeError as e:
        print(f"Config is not valid JSON: {e}")
        raise


@app.command()
def main(
    filename: Annotated[str, typer.Argument(help="The test to run")] = "locustfile.py",
    users: Annotated[int, typer.Option("-u", "--users", help="Number of concurrent VUs (peak)")] = 1,
    duration: Annotated[int | None, typer.Option("-d", "--duration", help="Time to run the test (seconds)")] = None,
    rate: Annotated[float | None, typer.Option("-r", "--rate", help="Number of users to spawn (per second)")] = None,
    iterations: Annotated[
        int | None, typer.Option("-i", "--iterations", help="Max total number of iterations to run")
    ] = None,
    instrument: Annotated[
        bool,
        typer.Option(
            "--instrument", help="Capture aiohttp traces and metrics using AioHttpClientInstrumentor().instrument()"
        ),
    ] = False,
    log_level: Annotated[
        LogLevel, typer.Option("--log-level", help="Set the logging level", case_sensitive=False)
    ] = LogLevel.info,
    config: Annotated[
        dict | None,
        typer.Option(
            metavar="JSON",
            parser=load_config,
            help='JSON string or path to JSON file, e.g. \n\n{"stages": [{"duration": 10, "target": 10}, {"duration": 5, "target": 0}]}',
        ),
    ] = None,
    event_loops: Annotated[
        int | None,
        typer.Option(
            "--event-loops", help="Set the number of aio event loops", rich_help_panel="Advanced Configuration"
        ),
    ] = None,
):
    log_level_id = getattr(logging, log_level.value.upper())
    setup_logging(log_level_id)

    file_path = Path(filename).resolve()
    if not file_path.exists():
        if filename == "locustfile.py":
            typer.echo(
                "Welcome to aiolocust! Create a locustfile.py in your current directory or specify a different one as an argument."
            )
            ctx = click.get_current_context()
            typer.echo(ctx.get_help())
        else:
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

    # apply --instrument option after loading script, so that any code based instrumentation takes precedence
    if instrument:
        from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor

        from aiolocust.users.http import request_hook

        AioHttpClientInstrumentor().instrument(request_hook=request_hook)

    # Return our two-tuple
    user_classes = {name: value for name, value in vars(module).items() if is_user_class(value)}
    if not user_classes and hasattr(module, "run"):

        class SimpleUser(HttpUser):
            async def run(self):
                pass  # This will be overwritten immediately, but needs to be here to satisfy the abstract base class requirement

        SimpleUser.run = module.run
        user_classes = {"SimpleUser": SimpleUser}

    if user_classes:
        r = Runner(
            [user for user in user_classes.values()],
            user_count=users,
            duration=duration,
            rate=rate,
            iterations=iterations,
            config=config,
            event_loops=event_loops,
        )
        r.run_test()
    else:
        typer.echo(f"Error: No User classes or run function defined in {filename}")
