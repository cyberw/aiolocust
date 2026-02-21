import asyncio
import io

from rich.console import Console
from utils import assert_search

from aiolocust.datatypes import Request
from aiolocust.stats import StatsFormatter, request


async def test_get_table():
    f = io.StringIO()
    console = Console(file=f)
    sf = StatsFormatter()
    console.print(sf.get_table())
    output = f.getvalue()
    f.seek(0)
    assert "Total" in output

    request(Request("foo", 1, 1, None))
    request(Request("foo", 1, 2, True))
    request(Request("bar", 1, 1, None))
    request(Request("bar", 1, 2, True))
    await asyncio.sleep(0.5)
    console.print(sf.get_table())
    output = f.getvalue()
    f.seek(0)
    assert "foo" in output
    assert "bar" in output
    assert "1500.0ms" in output
    assert "1 (50.0%)" in output
    assert_search(r"foo .* [234].\d{2}/s", output)
    assert_search(r"Total .* [67].\d{2}/s", output)

    await asyncio.sleep(0.1)
    console.print(sf.get_table(True))
    output = f.getvalue()
    f.seek(0)
    assert_search(r"foo .* [23].\d{2}/s", output)
    assert_search(r"Total .* [67].\d{2}/s", output)
    assert "1500.0ms" in output


async def test_error_pct_summary():
    f = io.StringIO()
    console = Console(file=f)
    sf = StatsFormatter()
    request(Request("foo", 1, 1, None))
    request(Request("foo", 2, 2, None))
    request(Request("bar", 3, 3, None))
    request(Request("bar", 4, 4, Exception("an exception")))
    request(Request("baz", 5, 5, True))
    await asyncio.sleep(0.5)
    console.print(sf.get_table(True))
    console.print(sf.get_error_table())
    output = f.getvalue()
    print(output)
    assert_search(r"foo .* 0 \(0.0%\)", output)
    assert_search(r"bar .* 1 \(50.0%\)", output)
    assert_search(r"baz .* 1 \(100.0%\)", output)
    assert_search(r"Total .* 2 \(40.0%\)", output)

    assert_search(r"foo .* 1500.0ms", output)
    assert_search(r"bar .* 3500.0ms", output)
    assert_search(r"Total .* 3000.0ms .* 5000.0ms", output)

    assert "Error" in output
    assert_search(r"1 .* an exception", output)


async def test_error_cardinality():
    f = io.StringIO()
    console = Console(file=f)
    sf = StatsFormatter()
    for i in range(300):
        request(Request("foo", 1, 1, Exception(f"error with unique id {i}")))
    console.print(sf.get_error_table())
    output = f.getvalue()
    assert "Error" in output
    assert_search(r"1 .* error with unique id 0", output)
    assert_search(r"1 .* error with unique id 199", output)
    assert_search(r"100 .* OTHER", output)
