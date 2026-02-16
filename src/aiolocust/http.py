import time
from asyncio import Future
from collections.abc import Callable, Coroutine
from typing import TYPE_CHECKING, Any

import aiohttp
from aiohttp import ClientConnectorError, ClientResponse, ClientResponseError, ClientSession
from aiohttp.client import _RequestContextManager
from opentelemetry import context
from opentelemetry.trace import Span

from aiolocust.datatypes import Request

if TYPE_CHECKING:  # avoid circular import
    from aiolocust.runner import Runner


SPAN_NAME_KEY = context.create_key("name")


class LocustResponse(ClientResponse):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.error: Exception | bool | str | None = None


class LocustRequestContextManager(_RequestContextManager):
    def __init__(self, request_handler: Callable, name, coro: Coroutine[Future[Any], None, ClientResponse]):
        super().__init__(coro)
        # slightly hacky way to get the URL, but passing it explicitly would be a mess
        # and it is only used for connection errors where the exception doesn't contain URL
        self.str_or_url = coro._coro.cr_frame.f_locals["str_or_url"]  # type: ignore
        self.request_handler = request_handler
        self._resp: LocustResponse  # type: ignore
        self.name = name

    async def __aenter__(self) -> LocustResponse:
        ctx = context.set_value(SPAN_NAME_KEY, self.name)
        token = context.attach(ctx)
        self.start_time = time.perf_counter()
        try:
            await super().__aenter__()
        except ClientConnectorError as e:
            elapsed = self.ttlb = time.perf_counter() - self.start_time
            if request_info := getattr(e, "request_info", None):
                url = request_info.url
            else:
                url = self.str_or_url
            self.request_handler(Request(str(self.name or url), elapsed, elapsed, e))
            raise
        except ClientResponseError as e:
            elapsed = self.ttlb = time.perf_counter() - self.start_time
            self.request_handler(Request(str(self.name or self.str_or_url), elapsed, elapsed, e))
            raise
        except TimeoutError as e:
            elapsed = self.ttlb = time.perf_counter() - self.start_time
            self.request_handler(Request(str(self.name or self.str_or_url), elapsed, elapsed, e))
            raise
        else:
            self.url = super()._resp.url
            self.ttfb = time.perf_counter() - self.start_time
            await self._resp.read()
            self.ttlb = time.perf_counter() - self.start_time
        finally:
            context.detach(token)

        return self._resp

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await super().__aexit__(exc_type, exc_val, exc_tb)
        if self._resp.error is None:  # no explicit value set in with-block
            try:
                self._resp.raise_for_status()
            except (ClientResponseError, ClientConnectorError) as e:
                self._resp.error = e
            if exc_val:  # overwrite if there was an explicit exception (e.g. an assert or crash)
                self._resp.error = exc_val
        self.request_handler(
            Request(
                str(self.name or self.url),
                self.ttfb,
                self.ttlb,
                self._resp.error,
            )
        )


def request_hook(span: Span, params: aiohttp.TraceRequestStartParams):  # noqa: ARG001
    """
    Request hook for renaming spans based on name parameter (passed via context vars)

    Typical usage:

    AioHttpClientInstrumentor().instrument(request_hook=aiolocust.http.request_hook)
    """
    if custom_name := context.get_value(SPAN_NAME_KEY):
        span.update_name(str(custom_name))


class LocustClientSession(ClientSession):
    def __init__(self, request_handler: Callable, runner: Runner | None = None, base_url=None, **kwargs):
        super().__init__(base_url=base_url, response_class=LocustResponse, **kwargs)
        self.runner: Runner = runner  # pyright: ignore[reportAttributeAccessIssue] # always set outside of unit testing
        self._request_handler = request_handler

    # explicitly declare this to get the correct return type and enter session
    async def __aenter__(self) -> LocustClientSession:
        return self

    def get(self, url, *, name=None, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(self._request_handler, name, super().get(url, **kwargs))

    def post(self, url, *, name=None, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(self._request_handler, name, super().post(url, **kwargs))

    def options(self, url, *, name=None, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(self._request_handler, name, super().options(url, **kwargs))

    def head(self, url, *, name=None, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(self._request_handler, name, super().head(url, **kwargs))

    def put(self, url, *, name=None, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(self._request_handler, name, super().put(url, **kwargs))

    def patch(self, url, *, name=None, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(self._request_handler, name, super().patch(url, **kwargs))

    def delete(self, url, *, name=None, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(self._request_handler, name, super().delete(url, **kwargs))
