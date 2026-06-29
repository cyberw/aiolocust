import sys
import threading
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


@dataclass(slots=True)
class Request:
    name: str
    ttfb: float
    ttlb: float
    error: Exception | bool | str | None


@dataclass(slots=True)
class RequestEntry:
    count: int = 0
    errorcount: int = 0
    sum_ttlb: float = 0.0
    max_ttlb: float = 0.0

    def __iadd__(self, other: RequestEntry):
        if isinstance(other, RequestEntry):
            self.count += other.count
            self.errorcount += other.errorcount
            self.sum_ttlb += other.sum_ttlb
            self.max_ttlb = max(self.max_ttlb, other.max_ttlb)
            return self

    def rate(self, start, end) -> float:
        return self.count / (end - start)

    @property
    def avg_ttlb(self) -> float:
        return self.sum_ttlb / self.count if self.count > 0 else 0.0

    @property
    def avg_ttlb_ms(self) -> float:
        return self.avg_ttlb * 1000

    @property
    def max_ttlb_ms(self) -> float:
        return self.max_ttlb * 1000

    @property
    def error_percentage(self) -> float:
        return self.errorcount / self.count * 100.0 if self.count > 0 else 0.0


@dataclass
class Stage:
    duration: float
    target: int


class LogLevel(StrEnum):
    debug = "debug"
    info = "info"
    warning = "warning"
    error = "error"


@dataclass
class Config:
    # used for giving all modules access to command line arguments. Remember to keep this in sync with main() arguments.
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


class SafeCounter:
    """A thread-safe counter."""

    def __init__(self, limit: int | None = None):
        self.value = 0
        self.limit = limit if limit is not None else sys.maxsize
        self.lock = threading.Lock()

    def increment(self) -> bool:
        with self.lock:
            if self.value < self.limit:
                self.value += 1
                return False
            return True
