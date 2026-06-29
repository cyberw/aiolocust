import importlib.util
import inspect
import json
import logging
import os
import sys
import traceback
from importlib.metadata import version
from pathlib import Path
from typing import Annotated

import click
import typer

import aiolocust
from aiolocust.datatypes import LogLevel
from aiolocust.otel import configure_telemetry

app = typer.Typer(add_completion=False)
logger = logging.getLogger(__name__)
# avoid annoying "Using selector: KqueueSelector" when running in debug:
logging.getLogger("asyncio").setLevel(logging.INFO)
# dont debug log urllib3, because it is very verbose,
# and would send logs to OTEL about having written to the collector,
# which is extra weird
logging.getLogger("urllib3").setLevel(logging.INFO)


def load_config(input_string: str) -> dict:
    if os.path.isfile(input_string):
        try:
            with open(input_string) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            print(f"--config file is not valid JSON: {e}")
            raise
        except Exception as e:
            print(f"--config file could not be opened: {e}")
            raise
    try:
        return json.loads(input_string)
    except json.JSONDecodeError as e:
        print(f"--config string is not valid JSON: {e}")
        raise


def version_callback(value: bool):
    if value:
        print(f"aiolocust {version('aiolocust')}")
        raise typer.Exit()


@app.command(context_settings={"auto_envvar_prefix": "LOCUST"})
def main(
    filename: Annotated[
        str,
        typer.Argument(
            help="The test to run",
            envvar="LOCUST_FILENAME",  # auto_envvar_prefix doesn't work with arguments for some reason
        ),
    ] = "locustfile.py",
    users: Annotated[int, typer.Option("-u", "--users", help="Number of concurrent VUs (peak)")] = 1,
    duration: Annotated[int | None, typer.Option("-d", "--duration", help="Time to run the test (seconds)")] = None,
    rate: Annotated[float | None, typer.Option("-r", "--rate", help="Number of users to spawn (per second)")] = None,
    iterations: Annotated[
        int | None, typer.Option("-i", "--iterations", help="Max total number of iterations to run")
    ] = None,
    host: Annotated[str | None, typer.Option("-H", "--host", help="Base URL to target")] = None,
    instrument: Annotated[
        bool,
        typer.Option(
            "--instrument", help="Capture aiohttp traces and metrics using AioHttpClientInstrumentor().instrument()"
        ),
    ] = False,
    log_level: Annotated[
        LogLevel,
        typer.Option(
            "-l",
            "--log-level",
            help="Set the logging level (debug, info, warning, error)",
            case_sensitive=False,
            metavar="TEXT",
            show_default=False,
        ),
    ] = LogLevel.info,
    config: Annotated[
        dict | None,
        typer.Option(
            metavar="JSON",
            parser=load_config,
            help='JSON string or path to JSON file, e.g. \n\n{"stages":[{"duration":10,"target":10},{"duration":5,"target":0}]}',
        ),
    ] = None,
    event_loops: Annotated[
        int | None,
        typer.Option(
            "--event-loops", help="Set the number of aio event loops", rich_help_panel="Advanced Configuration"
        ),
    ] = None,
    html_report: Annotated[
        Path | None,
        typer.Option("--html-report", help="Write the final summary as a static HTML report"),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            help="A description of the test run to include in otel resource attributes,\n\nto differentiate between runs with the same file name",
        ),
    ] = None,
    _version: bool = typer.Option(
        None,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show the version and exit.",
        show_envvar=False,
    ),
):
    # propagate command line args to other modules via config object
    for key, value in locals().items():
        setattr(aiolocust.config, key, value)

    log_level_id = getattr(logging, log_level.value.upper())

    configure_telemetry()

    # delayed imports so that logging is configured first
    from aiolocust import HttpUser, User
    from aiolocust.runner import Runner

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

    spec = importlib.util.spec_from_file_location(
        module_name,
        file_path,
        submodule_search_locations=[str(file_path.parent)],
    )
    if spec is None or spec.loader is None:
        typer.echo(f"Error: Could not load the file at {file_path}")
        raise typer.Exit(code=1)

    module = importlib.util.module_from_spec(spec)

    # Add the module to sys.modules so it behaves like a normal import
    sys.modules[module_name] = module

    SDK_ROOT = Path(__file__).resolve().parent

    def is_ignored_frame(tb):
        filename = tb.tb_frame.f_code.co_filename

        # 1. Skip frozen / synthetic frames
        if filename.startswith("<") and filename.endswith(">"):
            return True

        # 2. Skip your SDK frames
        try:
            path = Path(filename).resolve()
            if path.is_relative_to(SDK_ROOT):
                return True
        except Exception:
            pass

        return False

    # Run any top-level code
    try:
        spec.loader.exec_module(module)
    except BaseException as exc:
        # if there's an error during import, print the traceback for the user code, but leave out aiolocust and importlib
        tb = exc.__traceback__
        logger.debug(f"Error during import of {filename}: {exc}")
        while tb and is_ignored_frame(tb):
            tb = tb.tb_next

        traceback.print_exception(type(exc), exc, tb)
        raise SystemExit(1)

    # apply --instrument option after loading script, so that any code based instrumentation takes precedence
    if instrument:
        from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor

        AioHttpClientInstrumentor().instrument()

    def is_user_class(item) -> bool:
        """
        Check if a variable is a runnable (non-abstract) User class
        """
        return bool(inspect.isclass(item)) and issubclass(item, User) and not inspect.isabstract(item)

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
            host=host,
            config=config,
            event_loops=event_loops,
            html_report=html_report,
        )
        r.run_test()
    else:
        typer.echo(f"Error: No User classes or run function defined in {filename}")


# Expose a Click command object for mkdocs-click documentation generation.
cli = typer.main.get_command(app)
