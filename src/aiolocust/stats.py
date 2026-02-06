import time
from collections import defaultdict
from threading import Lock

from opentelemetry import metrics, trace
from opentelemetry.sdk.metrics import (
    Histogram,
    MeterProvider,
)
from opentelemetry.sdk.metrics.export import (
    AggregationTemporality,
    HistogramDataPoint,
    InMemoryMetricReader,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from rich.console import Console
from rich.table import Table

from aiolocust.datatypes import Request, RequestEntry

MAX_ERROR_KEYS = 200

reader = InMemoryMetricReader(
    preferred_temporality={
        Histogram: AggregationTemporality.DELTA,
    }
)

resource = Resource.create(
    {
        "service.name": "locust",
        "service.version": "0.0.0",  # __version__
    }
)
trace.set_tracer_provider(TracerProvider(resource=resource))
metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[reader]))
meter = metrics.get_meter("locust")
ttlb_histogram = meter.create_histogram("http.client.duration")


class Stats:
    def __init__(self, console: Console | None = None):
        self._console = console if console else Console()
        self.start_time = time.time()
        self.last_time = self.start_time
        self.total: dict[str, RequestEntry] = defaultdict(lambda: RequestEntry(0, 0, 0, 0, 0))
        self.error_counter = defaultdict(int)
        self.error_counter_lock = Lock()

    def record_error(self, key: str):
        with self.error_counter_lock:
            if key not in self.error_counter and len(self.error_counter) >= MAX_ERROR_KEYS:
                key = "OTHER"
            self.error_counter[key] += 1

    def request(self, req: Request):
        attributes = {
            "http.url": req.url,
            # the rest of these remain to be implemented
            # http.method=GET,
            # http.host=localhost,
            # net.peer.name=localhost,
            # net.peer.port=8080,
            # http.status_code=200}
        }
        if req.error:
            attributes["error.type"] = req.error.__class__.__name__
            self.record_error(str(req.error))
        ttlb_histogram.record(req.ttlb, attributes=attributes)

    def _get_entries(self) -> dict[str, RequestEntry]:
        metrics_data = reader.get_metrics_data()
        entries: dict[str, RequestEntry] = defaultdict(lambda: RequestEntry(0, 0, 0, 0, 0))
        for resource_metric in metrics_data.resource_metrics if metrics_data else []:
            for scope_metric in resource_metric.scope_metrics:
                for metric in scope_metric.metrics:
                    for point in metric.data.data_points:
                        if not point.attributes:
                            raise Exception(f"A data point had no attributes, that should never happen. Point: {point}")
                        if not isinstance(point, HistogramDataPoint):
                            raise Exception(f"Unexpected datapoint type: {point}")
                        re = entries[str(point.attributes["http.url"])]
                        if point.attributes.get("error.type"):
                            re.errorcount = point.count
                        re.count += point.count
                        re.max_ttlb = max(point.max, re.max_ttlb)
                        re.sum_ttlb += point.sum
        return entries

    def print_table(self, final_summary=False):
        table = Table(show_edge=False)
        table.add_column("Name", max_width=30)
        table.add_column("Count", justify="right")
        table.add_column("Failures", justify="right")
        table.add_column("Avg", justify="right")
        table.add_column("Max", justify="right")
        table.add_column("Rate", justify="right")
        now = time.time()

        entries = self._get_entries()

        total_ttlb = 0
        total_max_ttlb = 0
        total_count = 0
        total_errorcount = 0
        total_rate = 0

        for url, re in entries.items():
            self.total[url].count += re.count
            self.total[url].errorcount += re.errorcount
            self.total[url].sum_ttlb += re.sum_ttlb
            self.total[url].max_ttlb = max(self.total[url].max_ttlb, re.max_ttlb)
            error_percentage = re.errorcount / re.count * 100
            rate = re.count / (now - self.last_time)
            if not final_summary:
                table.add_row(
                    url,
                    str(re.count),
                    f"{re.errorcount} ({error_percentage:2.1f}%)",
                    f"{re.sum_ttlb / re.count * 1000:4.1f}ms",
                    f"{re.max_ttlb * 1000:4.1f}ms",
                    f"{rate:.2f}/s",
                )
            total_ttlb += re.sum_ttlb
            total_max_ttlb = max(total_max_ttlb, re.max_ttlb)
            total_count += re.count
            total_errorcount += re.errorcount
            total_rate += rate

        total_error_percentage = total_errorcount / total_count * 100 if total_count else 0
        total_avg_ttlb_ms = total_ttlb / total_count * 1000 if total_count else 0
        if not final_summary:
            table.add_row(
                "Total",
                str(total_count),
                f"{total_errorcount} ({total_error_percentage:2.1f}%)",
                f"{total_avg_ttlb_ms:4.1f}ms",
                f"{total_max_ttlb:4.1f}ms",
                f"{total_rate:.2f}/s",
            )

        if final_summary:
            table.title = "Summary"
            total_ttlb = 0
            total_max_ttlb = 0
            total_count = 0
            total_errorcount = 0
            total_rate = 0
            for url, re in self.total.items():
                total_ttlb += re.sum_ttlb
                total_max_ttlb = max(total_max_ttlb, re.max_ttlb)
                rate = re.count / (now - self.start_time)
                total_rate += rate
                total_count += re.count
                total_errorcount += re.errorcount
                error_percentage = re.errorcount / re.count * 100
                table.add_row(
                    url,
                    str(re.count),
                    f"{re.errorcount} ({error_percentage:2.1f}%)",
                    f"{re.sum_ttlb / re.count * 1000:4.1f}ms",
                    f"{re.max_ttlb * 1000:4.1f}ms",
                    f"{rate:.2f}/s",
                )
            total_error_percentage = total_errorcount / total_count * 100 if total_count else 0
            total_avg_ttlb_ms = total_ttlb / total_count * 1000 if total_count else 0
            table.add_row(
                "Total",
                str(total_count),
                f"{total_errorcount} ({total_error_percentage:2.1f}%)",
                f"{total_avg_ttlb_ms:4.1f}ms",
                f"{total_max_ttlb * 1000:4.1f}ms",
                f"{total_rate:.2f}/s",
            )
        else:
            self._console.print()

        self.last_time = time.time()

        self._console.print(table)

        if final_summary and self.error_counter:
            self._console.print()
            error_table = Table(show_edge=False)

            error_table.add_column("Count")
            error_table.add_column("Error")

            for key, count in sorted(self.error_counter.items(), key=lambda item: item[1], reverse=True):
                error_table.add_row(str(count), key)
            self._console.print(error_table)

        return
