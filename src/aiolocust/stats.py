import time
from collections import defaultdict

from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    HistogramDataPoint,
    InMemoryMetricReader,
)
from opentelemetry.sdk.resources import Resource
from rich.console import Console
from rich.table import Table

from aiolocust.datatypes import Request, RequestEntry


class Stats:
    def __init__(self, console: Console | None = None):
        self._console = console if console else Console()
        self.reader = InMemoryMetricReader()
        self.resource = Resource.create({"service.name": "locust"})
        self.provider = MeterProvider(resource=self.resource, metric_readers=[self.reader])
        self.meter = self.provider.get_meter("my_meter")
        self.ttlb_histogram = self.meter.create_histogram("http.client.duration")
        self.start_time = time.time()
        self.last_time = self.start_time
        self.total: dict[str, RequestEntry] = defaultdict(lambda: RequestEntry(0, 0, 0, 0, 0))

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
        self.ttlb_histogram.record(req.ttlb, attributes=attributes)

    def _get_entries(self) -> dict[str, RequestEntry]:
        metrics_data = self.reader.get_metrics_data()
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
            error_percentage = re.errorcount / re.count * 100
            rate = (re.count - self.total[url].count) / (now - self.last_time)
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

        # Prepare for next batch, and possibly the final summary
        total_ttlb = 0
        total_max_ttlb = 0
        total_count = 0
        total_errorcount = 0
        total_rate = 0
        for url, re in entries.items():
            self.total[url] = re
            if final_summary:
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

        if final_summary:
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

        self.last_time = time.time()

        self._console.print()
        if final_summary:
            table.title = "Summary"
        self._console.print(table)
        return
