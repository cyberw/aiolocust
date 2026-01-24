# AIOLocust

This is a 2026 reimagining of [Locust](https://github.com/locustio/locust/). It is possible that we may merge the projects at some point, but for now it is a separate library.

**!!! This is pre-alpha software, not production ready !!!**

## Installation

We recommend using [uv](https://docs.astral.sh/uv/getting-started/installation/) for installation

```text
uv tool install aiolocust
aiolocust --help
```

There are also some [alternative ways to install](#alternative-ways-to-install).

## Create a locustfile

```python
import asyncio
from aiolocust import LocustClientSession

async def run(client: LocustClientSession):
    async with client.get("http://example.com/") as resp:
        assert resp.status == 200
    await asyncio.sleep(0.1)
```

## Run a test

```text
aiolocust --run-time 5 --users 20
```

## Why?

### Simpler and more consistent syntax than Locust, leveraging asyncio instead of gevent

Locust was created in 2011, and while it has gone through several major overhauls, it still has a fair amount of legacy style code, and has accumulated a lot of non-core functionality that make it very hard to maintain and improve. It's 10000+ lines of code using a mix of procedural, object oriented and functional programming, with several confusing abstractions.

AIOLocust is built to be smaller in scope, but capture the learnings from Locust. It uses modern, explicitly asyncronous, Python code (instead of gevent/monkey patching).

It also further emphasizes the "It's just Python"-approach. If you, for example, want to take precise control of the ramp up and ramp down of a test, you shouldn't need to read the documentation, you should only need to know how to write code. We'll still provide the option of using prebuilt features too of course, but we'll try not to "build our users into a box".

### High performance

aiolocust is more performant than "regular" Locust because has a smaller footprint/complexity, but it's two main gains come from:

#### Using [asyncio](https://docs.python.org/3/library/asyncio.html) together with [aiohttp](https://docs.aiohttp.org/en/stable/)

aiolocust's performance is *much* better than HttpUser (based on Requests), and even slightly better than FastHttpUser (based on geventhttpclient). Because it uses async programming instead of monkey patching it is more useful on modern Python and more future-proof. Specifically it allows your locustfile to easily use asyncio libraries (like Playwright), which are becoming more and more common.

#### Leveraging Python in its [freethreading/no-GIL](https://docs.python.org/3/howto/free-threading-python.html) form

This means that you dont need to launch one Locust process per core! And even if your load tests are doing some heavy computations, they are less likely to impact eachother, as one thread will not block Python from concurrently working on another one.

Users/threads can also communicate easily with eachother, as they are in the same process, unlike in the old Locust implementation where you were forced to use zmq messaging between master and worker processes and worker-to-worker communication was nearly impossible.

## Some actual numbers

For example, aiolocust can do almost 70k requests/s on a MacBook Pro M3. It is also much faster to start than regular Locust, and has no issues spawning a lot of new users in a short interval.

```text
  Name                   ┃   Count ┃ Failures ┃     Avg ┃        Max ┃       Rate
 ━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━
  http://localhost:8080/ │ 2032741 │ 0 (0.0%) │   2.8ms │     35.8ms │ 67659.22/s
 ────────────────────────┼─────────┼──────────┼─────────┼────────────┼────────────
  Total                  │   2.8ms │   35.8ms │ 2032741 │ 67659.22/s │
```

## Things this doesn't have compared do Locust (at least not yet)

* A WebUI
* Support for distributed tests
* Polish. This is not ready for production use yet.

## Alternative ways to install

If your tests need additional packages, or you want to structure your code in a complete Python project, here's how:

```text
uv init --python 3.14t
uv add aiolocust
uv run aiolocust --help
```

Install for developing aiolocust, or just getting the latest changes before they make it into a release:

```text
git clone https://github.com/cyberw/aiolocust.git
cd aiolocust
uv run aiolocust --run-time 5 --users 20
```
