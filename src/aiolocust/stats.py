import time

from rich.console import Console
from rich.table import Table

from aiolocust.datatypes import Request, RequestEntry, RequestTimeSeries


class Stats:
    def __init__(self, console: Console | None = None):
        self._console = console if console else Console()
        self.requests: dict[str, RequestTimeSeries] = {}
        self.start_time: float = time.perf_counter()

    def reset(self):
        self.start_time: float = time.perf_counter()
        self.requests.clear()

    def request(self, req: Request):
        t = int(time.time())
        if req.url not in self.requests:
            self.requests[req.url] = RequestTimeSeries()

        rts = self.requests[req.url]
        with rts.lock:
            if t not in rts.buckets:
                rts.buckets[t] = RequestEntry(1, 1 if req.error else 0, req.ttfb, req.ttlb, req.ttlb)
            else:
                re = rts.buckets[t]

                re.count += 1
                if req.error:
                    re.errorcount += 1
                re.sum_ttfb += req.ttfb
                re.sum_ttlb += req.ttlb
                re.max_ttlb = max(re.max_ttlb, req.ttlb)

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
