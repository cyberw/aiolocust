import asyncio
import time
from collections.abc import Awaitable
from contextlib import AbstractAsyncContextManager
from typing import Protocol

import aiohttp
from aiohttp import ClientSession


class ResponseContextManagerProtocol(
    Awaitable[aiohttp.ClientResponse],
    AbstractAsyncContextManager[aiohttp.ClientResponse],
    Protocol,
): ...


class WrappedResponseManager:
    def __init__(self, response_cm):
        self.response_cm = response_cm
        self.start_time = None

    async def __aenter__(self):
        self.start_time = time.perf_counter()
        resp = await self.response_cm.__aenter__()
        self.elapsed = time.perf_counter() - self.start_time
        return resp

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        suppress = await self.response_cm.__aexit__(exc_type, exc_val, exc_tb)
        print(self.elapsed)
        return suppress


class LocustClientSession(ClientSession):
    def get(self, url, **kwargs):
        return WrappedResponseManager(super().get(url, **kwargs))


async def on_request_end(session, trace_config_ctx, params):  # noqa: ARG001
    trace_config_ctx.elapsed = time.perf_counter() - trace_config_ctx.start


async def on_request_start(session, trace_config_ctx, params):  # noqa: ARG001
    trace_config_ctx.start = time.perf_counter()


async def user(client: ClientSession):
    await fetch(client)


async def fetch(client: ClientSession):
    async with client.get("/") as resp:
        assert resp.status == 200
        return await resp.text()


async def main():
    trace_config = aiohttp.TraceConfig()
    trace_config.on_request_start.append(on_request_start)
    trace_config.on_request_end.append(on_request_end)

    while True:
        async with LocustClientSession(
            "https://www.locust.cloud", trace_configs=[trace_config]
        ) as client:
            await user(client)
        await asyncio.sleep(1)


asyncio.run(main())
