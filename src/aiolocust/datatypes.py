from dataclasses import dataclass


@dataclass(slots=True)
class Request:
    url: str
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
