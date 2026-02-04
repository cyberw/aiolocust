import asyncio
import io

from rich.console import Console
from utils import assert_search

from aiolocust.datatypes import Request
from aiolocust.stats import Stats


async def test_stats():
    f = io.StringIO()
    stats = Stats(Console(file=f))
    stats.print_table()
    output = f.getvalue()
    f.seek(0)
    print(output)
    assert "Total" in output

    stats.request(Request("foo", 1, 1, None))
    stats.request(Request("foo", 1, 2, True))
    stats.request(Request("bar", 1, 1, None))
    stats.request(Request("bar", 1, 2, True))
    await asyncio.sleep(0.5)
    stats.print_table()
    output = f.getvalue()
    f.seek(0)
    print(output)
    assert "foo" in output
    assert "bar" in output
    assert "1500.0ms" in output
    assert "1 (50.0%)" in output
    assert_search(r"foo .* [234].\d{2}/s", output)
    assert_search(r"Total .* [67].\d{2}/s", output)

    await asyncio.sleep(0.1)
    stats.print_table(True)
    output = f.getvalue()
    f.seek(0)
    print(output)
    assert_search(r"foo .* [23].\d{2}/s", output)
    assert_search(r"Total .* [67].\d{2}/s", output)
    assert "1500.0ms" in output


async def test_error_pct_summary():
    f = io.StringIO()
    stats = Stats(Console(file=f))
    stats.request(Request("foo", 1, 1, None))
    stats.request(Request("foo", 2, 2, None))
    stats.request(Request("bar", 3, 3, None))
    stats.request(Request("bar", 4, 4, True))
    stats.request(Request("baz", 5, 5, True))
    await asyncio.sleep(0.5)
    stats.print_table(True)
    output = f.getvalue()
    print(output)
    assert_search(r"foo .* 0 \(0.0%\)", output)
    assert_search(r"bar .* 1 \(50.0%\)", output)
    assert_search(r"baz .* 1 \(100.0%\)", output)
    assert_search(r"Total .* 2 \(40.0%\)", output)

    assert_search(r"foo .* 1500.0ms", output)
    assert_search(r"bar .* 3500.0ms", output)
    assert_search(r"Total .* 3000.0ms .* 5000.0ms", output)
