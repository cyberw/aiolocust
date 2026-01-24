import threading
from dataclasses import dataclass, field


@dataclass(slots=True)
class Request:
    url: str
    ttfb: float
    ttlb: float
    error: Exception | bool | None


@dataclass(slots=True)
class RequestEntry:
    count: int
    errorcount: int
    sum_ttfb: float
    sum_ttlb: float
    max_ttlb: float
    lock: threading.Lock = field(default_factory=threading.Lock)
