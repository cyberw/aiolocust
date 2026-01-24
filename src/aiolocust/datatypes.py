from dataclasses import dataclass

from .util import Counter


@dataclass(slots=True)
class Request:
    url: str
    ttfb: float
    ttlb: float
    error: Exception | bool | None


@dataclass(slots=True)
class RequestEntry:
    count: Counter
    errorcount: Counter
    sum_ttfb: float
    sum_ttlb: float
    max_ttlb: float
