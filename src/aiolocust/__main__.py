# Allow running as `python -m aiolocust` — invoke the Typer app so
# command-line arguments are parsed instead of calling the command
# function directly which ignores `sys.argv`.

from aiolocust.cli import app

if __name__ == "__main__":
    app()
