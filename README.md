# aiolocust

[![PyPI](https://img.shields.io/pypi/v/aiolocust.svg)](https://pypi.org/project/aiolocust/)
![Python Version from PEP 621 TOML](https://img.shields.io/python/required-version-toml?tomlFilePath=https%3A%2F%2Fraw.githubusercontent.com%2Fcyberw%2Faiolocust%2Fmaster%2Fpyproject.toml)
[![Downloads](https://static.pepy.tech/personalized-badge/aiolocust?period=total&units=INTERNATIONAL_SYSTEM&left_color=GREY&right_color=GREEN&left_text=downloads)](https://pepy.tech/projects/aiolocust)
[![Build Status](https://github.com/cyberw/aiolocust/workflows/Tests/badge.svg)](https://github.com/cyberw/aiolocust/actions?query=workflow%3ATests)

This is a 2026 reimagining of the load testing tool [Locust](https://github.com/locustio/locust/).

It has a ton of [advantages over its predecessor](#simple-and-consistent-syntax), but is still in alpha and missing many of Locust's more advanced features. Do let us know if you find any major issues or want to contribute though!

## Installation

We recommend using [uv](https://docs.astral.sh/uv/getting-started/installation/)

```text
uv tool install aiolocust
aiolocust --help
```

There are also some [alternative ways to install](#alternative-ways-to-install).

## Create a locustfile.py

```python
import asyncio
from aiolocust import HttpUser

async def run(user: HttpUser):
    async with user.client.get("http://example.com/") as resp:
        pass
    async with user.client.get("http://example.com/") as resp:
        # extra validation, not just HTTP response code:
        assert "expected text" in await resp.text()
    await asyncio.sleep(0.1)
```

See [more examples](examples/).

## Run a test

```text
aiolocust --duration 30 --users 100
```

```text
 Name                   ┃  Count ┃ Failures ┃    Avg ┃    Max ┃       Rate
━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━
 http://example.com/    │ 120779 │ 0 (0.0%) │  1.6ms │ 22.6ms │ 60372.44/s
────────────────────────┼────────┼──────────┼────────┼────────┼────────────
 Total                  │ 120779 │ 0 (0.0%) │  1.6ms │ 22.6ms │ 60372.44/s

 Name                   ┃  Count ┃ Failures ┃    Avg ┃    Max ┃       Rate
━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━
 http://example.com     │ 243411 │ 0 (0.0%) │  1.6ms │ 22.6ms │ 60800.63/s
────────────────────────┼────────┼──────────┼────────┼────────┼────────────
 Total                  │ 243411 │ 0 (0.0%) │  1.6ms │ 22.6ms │ 60800.63/s
...
 Name                   ┃   Count ┃ Failures ┃    Avg ┃    Max ┃       Rate
━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━
 http://example.com/    │ 1836384 │ 0 (0.0%) │  1.6ms │ 22.6ms │ 61154.84/s
────────────────────────┼─────────┼──────────┼────────┼────────┼────────────
 Total                  │ 1836385 │ 0 (0.0%) │  1.6ms │ 22.6ms │ 61154.87/s
```

## Why a rewrite instead of just expanding Locust?

Locust was created in 2011, and while it has gone through several major overhauls, it still has a lot of legacy-style code, and has accumulated a lot of non-core functionality that makes it very hard to maintain and improve. It has over 10,000 lines of code, with a mix of procedural, object oriented and functional programming, with several confusing abstractions.

aiolocust is built to be smaller in scope, but capture the learnings from Locust. It is possible that this could be merged into Locust at some point, but for now it is a completely separate package.

## Simple and consistent syntax

Tests are expressed in modern, explicitly asynchronous code, instead of relying on gevent monkey patching, and implicit concurrency.

It has fewer "gotcha's" and better type hinting, that should make it easier for humans as well as AIs to understand and write tests.

We also plan to further emphasize the "It's just Python"-approach. For example, if you want to take precise control of the ramp up and ramp down of a test, you shouldn't need to read the documentation, you should only need to know how to write code. We'll still provide the option of using prebuilt features too of course, but we'll make an effort not to box users in, which was sometimes the case with Locust.

## OTEL Native

aiolocust uses OTel for metrics internally and exporting them into your own monitoring solution is easy. Out of the box, it supports standard [OTel env vars](https://opentelemetry.io/docs/specs/otel/protocol/exporter/).

If you want traces and auto-instrumented metrics, it is easy to do [from code](examples/otel/instrument_aiohttpclient.py) or [using an agent](https://opentelemetry.io/docs/zero-code/python/).

Note: The "old" Locust supports exporting OTel traces/metrics as well, but this was "bolted on" and it used its own completely separate metrics tracking internally.

## High performance

aiolocust is more performant than "regular" Locust because it has a smaller footprint/complexity, but it's two main gains come from:

### 1. [asyncio](https://docs.python.org/3/library/asyncio.html) + [aiohttp](https://docs.aiohttp.org/en/stable/)

aiolocust's performance is *much* better than HttpUser (based on Requests), and even slightly better than FastHttpUser (based on geventhttpclient). Because it uses async programming instead of monkey patching it is more useful on modern Python and more future-proof. Specifically it allows your locustfile to easily use asyncio libraries (like Playwright), which are becoming more and more common.

### 2. [Freethreading/no-GIL Python](https://docs.python.org/3/howto/free-threading-python.html)

This means that you don't need to launch one Locust process per CPU core. And even if your load tests happen to do some heavy computations, they are less likely to impact each other, as one thread will not block Python from concurrently working on another one.

Users/threads can also communicate easily with each other, as they are in the same process, unlike in the old Locust implementation where you were forced to use ZeroMQ messaging between master and worker processes and worker-to-worker communication was nearly impossible.

## Things this doesn't have compared do Locust (at least not yet)

* A WebUI
* Support for distributed tests
* Polish. This is not ready for production use yet.

## Alternative ways to install

If your tests need additional packages, or you want to structure your code in a complete Python project:

```text
uv init --python 3.14t
uv add aiolocust
uv run aiolocust --help
```

Install for developing the tool itself, or just getting the latest changes before they make it into a release:

```text
git clone https://github.com/cyberw/aiolocust.git
cd aiolocust
uv run aiolocust --help
```

You can still use good old pip as well, just remember that you need a freethreading Python build:

```text
pip install aiolocust
aiolocust --help
```
