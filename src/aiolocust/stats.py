import time

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    HistogramDataPoint,
    InMemoryMetricReader,
)
from opentelemetry.sdk.resources import Resource
from rich.console import Console
from rich.table import Table

from aiolocust.datatypes import Request

resource = Resource.create({"service.name": "locust"})
reader = InMemoryMetricReader()
provider = MeterProvider(resource=resource, metric_readers=[reader])
metrics.set_meter_provider(provider)
meter = metrics.get_meter("my_meter")
ttlb = meter.create_histogram("http.client.duration")
# ttfb = meter.create_histogram("http.client.duration")


class Stats:
    def __init__(self, console: Console | None = None):
        self._console = console if console else Console()
        self.storage = {}
        self.start_time = time.time()

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
        metrics_data = reader.get_metrics_data()
        assert metrics_data  # just for type checking
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
                        if not point.attributes:
                            raise Exception(f"A data point had no attributes, that should never happen. Point: {point}")
                        # Create a unique key for this specific metric + attribute combo
                        attr_items = tuple(sorted(point.attributes.items()))
                        metric_key = (metric.name, attr_items)
                        if isinstance(point, HistogramDataPoint):
                            current_val = point.count
                            # if point.attributes.get("error.type"):
                            #     current_err = point.count
                            # else:
                            #     current_val = point.count
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
                        url = None
                        for k, v in point.attributes.items():
                            if k == "http.url":
                                url = v
                            elif k == "":  # implement error tracking here
                                pass
                        avg_ttlb_ms = (point.sum / point.count) * 1000
                        max_ttlb_ms = point.max * 1000
                        table.add_row(
                            str(url),
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
        return
