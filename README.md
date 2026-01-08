# AIOLocust

This is a 2026 reimagining of [Locust](https://github.com/locustio/locust/). It is possible that we may merge the projects at some point, but for now it is a separate library.

## Simpler and more consistent syntax than Locust, leveraging asyncio

```python
import asyncio
from aiolocust import LocustClientSession

async def user(client: LocustClientSession):
    async with client.get("http://example.com/") as resp:
        assert resp.status == 200
    asyncio.sleep(0.1)
```

Locust was created in 2011, and while it has gone through several major overhauls, it has accumulated too much non-core functionality and design choices that make it very hard to maintain and improve. It's 10000+ lines of code using a mix of procedural, object oriented and functional programming.

AIOLocust is built to be smaller in scope, but capture the learnings from Locust. It uses modern, explicitly asyncronous, Python code (instead of gevent/monkey patching).

It also further emphasizes the "It's just Python"-approach. If you, for example, want to take precise control of the ramp up and ramp down of a test, you shouldn't need to read the documentation, you should only need to know how to write code. We'll still provide the option of using prebuilt features too of course, but we'll try not to "build our users into a box".

## High performance

aiolocust is more performant than "regular" Locust because has a smaller footprint/complexity, but it's two main gains come from:

### Using [asyncio](https://docs.python.org/3/library/asyncio.html) together with [aiohttp](https://docs.aiohttp.org/en/stable/).

aiolocust's performance is *much* better than HttpUser (based on Requests), and even slightly better than FastHttpUser (based on geventhttpclient). Because it uses async programming instead of monkey patching it is more useful on modern Python and more future-proof. Specifically it allows your locustfile to easily use asyncio libraries (like Playwright), which are becoming more and more common.

### Leveraging Python in its [freethreading/no-GIL](https://docs.python.org/3/howto/free-threading-python.html) form.

This means that you dont need to launch one locust process per core! Even if your load tests are doing some heavy computations, they are unlikely to impact eachother, as one thread will not block Python from running another one.

In fact, you can still use syncronous libraries, (without gevent monkey patching), just increase the number of threads.

Users/threads can also communicate easily with eachother, as they share memory with eachother, unlike in the old Locust implementation where you were forced to use zmq messaging between master and worker processes.

### Some actual numbers

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

## How to run the example

```text
git clone https://github.com/cyberw/aiolocust.git
cd aiolocust
uv run python locustfile.py
```
