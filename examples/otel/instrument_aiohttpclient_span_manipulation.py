# In aiohttp auto instrumentation, the span is closed as soon as the request is finished,
# so there is no way to manipulate the span inside the async with-block.
# But there are some workarounds:

import asyncio

import aiohttp
from opentelemetry import context
from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor
from opentelemetry.trace import Span

from aiolocust import LocustClientSession
from aiolocust.http import request_hook
from aiolocust.otel import tracer
from aiolocust.runner import Runner

SOME_ATTRIBUTE_KEY = context.create_key("some-attribute")


def response_hook(span: Span, params: aiohttp.TraceRequestEndParams | aiohttp.TraceRequestExceptionParams):  # noqa: ARG001
    if some_attribute := context.get_value(SOME_ATTRIBUTE_KEY):
        span.set_attribute("some-attribute", str(some_attribute))


AioHttpClientInstrumentor().instrument(request_hook=request_hook, response_hook=response_hook)


async def run(client: LocustClientSession):
    async with client.get("http://localhost:8080/", name="some-name") as resp:
        # autoinstrumented span is already closed here, so we can't manipulate it directly,
        # but aiolocust.http.request_hook renames the span based on the name parameter
        pass

    # we can create a parent span and do whatever we want with it
    with tracer.start_as_current_span("parent-span") as span:
        span.set_attribute("foo", "bar")
        async with client.get("http://localhost:8080/") as resp:
            pass

    # if we want to manipulate the span created by auto instrumentation,
    # we need to pass the information to the hooks via context vars:
    ctx = context.set_value(SOME_ATTRIBUTE_KEY, "some-value")
    token = context.attach(ctx)
    try:
        async with client.get("http://localhost:8080/") as resp:
            pass
    finally:
        context.detach(token)
    await asyncio.sleep(1)


if __name__ == "__main__":
    r = Runner()
    asyncio.run(r.run_test(run, 1, 2))
