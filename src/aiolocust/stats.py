import time

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    HistogramDataPoint,
    MetricExporter,
    MetricExportResult,
    MetricsData,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.resources import Resource
from rich.console import Console
from rich.table import Table

from aiolocust.datatypes import Request, RequestTimeSeries


class TableMetricExporter(MetricExporter):
    """A custom exporter that prints metrics in a CLI table format."""

    def __init__(self, *args, **kwargs):
        # Memory to store (last_value, last_time) for each unique metric
        self.storage = {}
        self.start_time = time.time()
        self._console = Console()
        super().__init__(*args, **kwargs)

    def export(self, metrics_data: MetricsData, timeout_millis: float = 10_000, **kwargs) -> MetricExportResult:
        table = Table(show_edge=False)
        table.add_column("Name", max_width=30)
        table.add_column("Count", justify="right")
        # table.add_column("Failures", justify="right")
        table.add_column("Avg", justify="right")
        table.add_column("Max", justify="right")
        table.add_column("Rate", justify="right")
        total_ttlb = 0
        total_max_ttlb = 0
        total_count = 0
        total_rate = 0
        # total_errorcount = 0
        now = time.time()
        for resource_metric in metrics_data.resource_metrics:
            for scope_metric in resource_metric.scope_metrics:
                for metric in scope_metric.metrics:
                    # Logic to handle different metric types (Sum, Gauge, etc.)
                    for point in metric.data.data_points:
                        # Flatten attributes into a string: "key=val, key2=val2"
                        # Create a unique key for this specific metric + attribute combo
                        if not point.attributes:
                            continue
                        attr_items = tuple(sorted(point.attributes.items()))
                        metric_key = (metric.name, attr_items)
                        if isinstance(point, HistogramDataPoint):
                            current_val = point.count
                        else:
                            print(f"Unexpected datapoint type: {point}")
                            continue

                        rate = 0.0

                        # Calculate rate if we have a previous data point
                        if metric_key in self.storage:
                            prev_val, prev_time = self.storage[metric_key]
                            delta_val = current_val - prev_val
                            delta_time = now - prev_time
                            if delta_time > 0:
                                rate = delta_val / delta_time
                            else:
                                rate = float("inf")  # not sure this can actually ever happen
                        else:
                            # assume program up time was startime.
                            # this will have issues repeated test runs without restart...
                            rate = current_val / (time.time() - self.start_time)

                        # Update storage for the next cycle
                        self.storage[metric_key] = (current_val, now)

                        # attrs = ", ".join([f"{k}={v}" for k, v in point.attributes.items()])
                        for k, v in point.attributes.items():
                            if k == "http.url":
                                url = v
                            elif k == "":  # implement error tracking here
                                pass
                        avg_ttlb_ms = (point.sum / point.count) * 1000
                        max_ttlb_ms = point.max * 1000
                        table.add_row(
                            url,
                            str(point.count),
                            # f"{errorcount} ({error_percentage:2.1f}%)",
                            f"{avg_ttlb_ms:4.1f}ms",
                            f"{max_ttlb_ms:4.1f}ms",
                            f"{rate:.2f}/s",
                        )
                        total_ttlb += point.sum
                        total_max_ttlb = max(total_max_ttlb, max_ttlb_ms)
                        total_count += point.count
                        total_rate += rate
                        # total_errorcount += errorcount

        table.add_row(
            "Total",
            str(total_count),
            # f"{total_errorcount} ({100 * total_errorcount / total_count:2.1f}%)",
            f"{1000 * total_ttlb / total_count:4.1f}ms",
            f"{total_max_ttlb:4.1f}ms",
            f"{total_rate:.2f}/s",
        )
        self._console.print()
        self._console.print(table)
        return MetricExportResult.SUCCESS

    def shutdown(self, timeout_millis: float = 30_000, **kwargs) -> None:
        pass

    def force_flush(self, timeout_millis: float = 30_000, **kwargs) -> bool:
        """Flush any buffered metrics. This exporter has no buffer, so succeed."""
        return True


resource = Resource.create({"service.name": "locust"})
exporter = TableMetricExporter()
reader = PeriodicExportingMetricReader(exporter, export_interval_millis=2000)

provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)

meter = metrics.get_meter("my_meter")
ttlb = meter.create_histogram("http.client.duration")
# ttfb = meter.create_histogram("http.client.duration")


class Stats:
    def __init__(self, console: Console | None = None):
        self._console = console if console else Console()
        self.requests: dict[str, RequestTimeSeries] = {}
        self.start_time: float = time.perf_counter()

    def reset(self):
        self.start_time: float = time.perf_counter()
        self.requests.clear()

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
        ttlb.record(req.ttlb, attributes=attributes)

    def print_table(self, summary=False):
        elapsed = time.perf_counter() - self.start_time
        current_second = int(time.time())
        total_ttlb = 0
        total_max_ttlb = 0
        total_count = 0
        total_errorcount = 0
        seconds_range = 0  # be calm, pyright...
        table = Table(show_edge=False)
        table.add_column("Name", max_width=30)
        table.add_column("Count", justify="right")
        table.add_column("Failures", justify="right")
        table.add_column("Avg", justify="right")
        table.add_column("Max", justify="right")
        table.add_column("Rate", justify="right")

        if summary:
            self._console.print()
            self._console.print("--------- Summary: ----------")

        for url, rts in self.requests.items():
            count = 0
            errorcount = 0
            sum_ttlb = 0
            max_ttlb = 0
            r = list(rts.buckets.keys()) if summary else range(current_second - 3, current_second - 1)
            seconds_range = len(r)
            for s in r:
                if bucket := rts.buckets.get(s):
                    count += bucket.count
                    errorcount += bucket.errorcount
                    sum_ttlb += bucket.sum_ttlb
                    max_ttlb = max(max_ttlb, bucket.max_ttlb)

            error_percentage = 100 * errorcount / count if count else 0
            avg_ttlb_ms = 1000 * sum_ttlb / count if count else 0
            max_ttlb_ms = 1000 * max_ttlb
            request_rate = count / elapsed if summary else count / seconds_range
            table.add_row(
                url,
                str(count),
                f"{errorcount} ({error_percentage:2.1f}%)",
                f"{avg_ttlb_ms:4.1f}ms",
                f"{max_ttlb_ms:4.1f}ms",
                f"{request_rate:.2f}/s",
            )
            total_ttlb += sum_ttlb
            total_max_ttlb = max(total_max_ttlb, max_ttlb)
            total_count += count
            total_errorcount += errorcount

        table.add_section()
        if total_count == 0:
            table.add_row(
                "Total",
                "0",
                "",
                "",
                "",
                "",
            )
        else:
            total_rate = total_count / elapsed if summary else total_count / seconds_range
            table.add_row(
                "Total",
                str(total_count),
                f"{total_errorcount} ({100 * total_errorcount / total_count:2.1f}%)",
                f"{1000 * total_ttlb / total_count:4.1f}ms",
                f"{1000 * total_max_ttlb:4.1f}ms",
                f"{total_rate:.2f}/s",
            )
            table.add_row("Run time", f"{elapsed:.1f}")
        self._console.print()
        self._console.print(table)
