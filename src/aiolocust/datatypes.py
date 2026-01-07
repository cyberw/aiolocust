from dataclasses import dataclass


@dataclass(slots=True)
class Request:
    url: str
    ttfb: float
    ttlb: float
    success: bool


@dataclass(slots=True)
class RequestEntry:
    count: int
    errorcount: int
    sum_ttfb: float
    sum_ttlb: float
    max_ttlb: float
