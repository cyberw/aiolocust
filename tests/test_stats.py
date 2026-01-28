import asyncio
import io
from contextlib import redirect_stdout

import pytest
from utils import assert_search

from aiolocust.datatypes import Request
from aiolocust.stats import Stats


@pytest.mark.asyncio
async def test_stats():
    stats = Stats()
    f = io.StringIO()
    with redirect_stdout(f):
        stats.print_table()

    output = f.getvalue()
    print(output)
    assert "Total" in output
    stats.request(Request("foo", 1, 1, None))
    stats.request(Request("foo", 1, 2, True))
    f = io.StringIO()
    with redirect_stdout(f):
        stats.print_table()

    output = f.getvalue()
    assert "foo" in output
    assert "0.00/s" in output
    await asyncio.sleep(2)
    f = io.StringIO()
    with redirect_stdout(f):
        stats.print_table()
    output = f.getvalue()
    print(output)
    assert "1500.0ms" in output
    assert "1 (50.0%)" in output
    assert "1.00/s" in output

    await asyncio.sleep(2)
    f = io.StringIO()
    with redirect_stdout(f):
        stats.print_table(True)

    output = f.getvalue()
    print(output)
    assert_search("foo .* 0.50/s", output)
    assert_search("Total .* 0.50/s", output)
    assert "1500.0ms" in output


@pytest.mark.asyncio
async def test_really_short_run():
    stats = Stats()
    stats.request(Request("foo", 1, 1, None))

    f = io.StringIO()
    with redirect_stdout(f):
        stats.print_table(True)

    output = f.getvalue()
    print(output)
    assert "foo" in output
