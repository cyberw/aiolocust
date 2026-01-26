import time

from rich.console import Console
from rich.table import Table

from .datatypes import Request, RequestEntry

start_time = 0
requests: dict[str, RequestEntry] = {}
console = Console()


def request(req: Request):
    if req.url not in requests:
        requests[req.url] = RequestEntry(1, 1 if req.error else 0, req.ttfb, req.ttlb, req.ttlb)
    else:
        re = requests[req.url]
        with re.lock:
            re.count += 1
            if req.error:
                re.errorcount += 1
            re.sum_ttfb += req.ttfb
            re.sum_ttlb += req.ttlb
            re.max_ttlb = max(re.max_ttlb, req.ttlb)


def print_table():
    requests_copy: dict[str, RequestEntry] = requests.copy()  # avoid mutation during print
    elapsed = time.perf_counter() - start_time
    total_ttlb = 0
    total_max_ttlb = 0
    total_count = 0
    total_errorcount = 0
    table = Table(show_edge=False)
    table.add_column("Name", max_width=30)
    table.add_column("Count", justify="right")
    table.add_column("Failures", justify="right")
    table.add_column("Avg", justify="right")
    table.add_column("Max", justify="right")
    table.add_column("Rate", justify="right")

    for url, re in requests_copy.items():
        table.add_row(
            url,
            str(re.count),
            f"{re.errorcount} ({100 * re.errorcount / re.count:2.1f}%)",
            f"{1000 * re.sum_ttlb / re.count:4.1f}ms",
            f"{1000 * re.max_ttlb:4.1f}ms",
            f"{re.count / elapsed:.2f}/s",
        )
        total_ttlb += re.sum_ttlb
        total_max_ttlb = max(total_max_ttlb, re.max_ttlb)
        total_count += re.count
        total_errorcount += re.errorcount
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
        table.add_row(
            "Total",
            str(total_count),
            f"{total_errorcount} ({100 * total_errorcount / total_count:2.1f}%)",
            f"{1000 * total_ttlb / total_count:4.1f}ms",
            f"{1000 * total_max_ttlb:4.1f}ms",
            f"{total_count / elapsed:.2f}/s",
        )
    print()
    console.print(table)
