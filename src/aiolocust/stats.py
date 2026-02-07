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
        self.aggregate: dict[str, RequestEntry] = defaultdict(RequestEntry)
        self.error_counter = defaultdict(int)
        self.error_counter_lock = Lock()
        _ = reader.get_metrics_data()  # clear

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
        entries: dict[str, RequestEntry] = defaultdict(RequestEntry)
        for resource_metric in metrics_data.resource_metrics if metrics_data else []:
            for scope_metric in resource_metric.scope_metrics:
                for metric in scope_metric.metrics:
                    for point in metric.data.data_points:
                        if not point.attributes:
                            raise Exception(f"A data point had no attributes, that should never happen. Point: {point}")
                        if not isinstance(point, HistogramDataPoint):
                            raise Exception(f"Unexpected datapoint type: {point}")
                        re = entries[str(point.attributes["http.url"])]
                        re.add_datapoint(
                            point.count, point.count if point.attributes.get("error.type") else 0, point.sum, point.max
                        )

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
        total = RequestEntry()

        for url, re in entries.items():
            self.aggregate[url] += re
            total += re
            if not final_summary:
                table.add_row(
                    url,
                    str(re.count),
                    f"{re.errorcount} ({re.error_percentage:2.1f}%)",
                    f"{re.avg_ttlb_ms:4.1f}ms",
                    f"{re.max_ttlb_ms:4.1f}ms",
                    f"{re.rate(self.last_time, now):.2f}/s",
                )

        if not final_summary:
            table.add_row(
                "Total",
                str(total.count),
                f"{total.errorcount} ({total.error_percentage:2.1f}%)",
                f"{total.avg_ttlb_ms:4.1f}ms",
                f"{total.max_ttlb:4.1f}ms",
                f"{total.rate(self.last_time, now):.2f}/s",
            )
            self._console.print()
        else:
            table.title = "Summary"
            total = RequestEntry()
            for url, re in self.aggregate.items():
                total += re
                table.add_row(
                    url,
                    str(re.count),
                    f"{re.errorcount} ({re.error_percentage:2.1f}%)",
                    f"{re.avg_ttlb_ms:4.1f}ms",
                    f"{re.max_ttlb_ms:4.1f}ms",
                    f"{re.rate(self.start_time, now):.2f}/s",
                )
            table.add_row(
                "Total",
                str(total.count),
                f"{total.errorcount} ({total.error_percentage:2.1f}%)",
                f"{total.avg_ttlb_ms:4.1f}ms",
                f"{total.max_ttlb_ms:4.1f}ms",
                f"{total.rate(self.start_time, now):.2f}/s",
            )

        self.last_time = now

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
