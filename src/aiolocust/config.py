# Used for giving easy access to command line arguments.
# If you make changes here, remember to keep it in sync with main() arguments
from enum import StrEnum
from pathlib import Path


class LogLevel(StrEnum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"


filename: str = "locustfile.py"
users: int = 1
duration: int | None = None
rate: float | None = None
iterations: int | None = None
host: str | None = None
instrument: bool = False
log_level: LogLevel = LogLevel.info
config: dict | None = None
event_loops: int | None = None
html_report: Path | None = None
profile: str | None = None
_version: bool = False
