import time
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from aiohttp import ClientConnectorError, ClientResponse, ClientResponseError, ClientSession
from aiohttp.client import _RequestContextManager

if TYPE_CHECKING:  # avoid circular import
    from aiolocust.runner import Runner


from aiolocust.datatypes import Request


class LocustResponse(ClientResponse):
    error: Exception | bool | None = None

    def __init__(self, *args, **kwargs):
        raise NotImplementedError()  # use wrap_response

    @classmethod
    def wrap_response(cls, resp: ClientResponse) -> LocustResponse:
        new = cast(LocustResponse, resp)
        new.error = None
        return new


class LocustRequestContextManager(_RequestContextManager):
    def __init__(self, request_handler: Callable, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # slightly hacky way to get the URL, but passing it explicitly would be a mess
        # and it is only used for connection errors where the exception doesn't contain URL
        self.str_or_url = args[0]._coro.cr_frame.f_locals["str_or_url"]
        self.request_handler = request_handler
        self._resp: LocustResponse  # type: ignore

    async def __aenter__(self) -> LocustResponse:
        self.start_time = time.perf_counter()
        try:
            await super().__aenter__()
        except ClientConnectorError as e:
            elapsed = self.ttlb = time.perf_counter() - self.start_time
            if request_info := getattr(e, "request_info", None):
                url = request_info.url
            else:
                url = self.str_or_url
            self.request_handler(Request(url, elapsed, elapsed, e))
            raise
        except ClientResponseError as e:
            elapsed = self.ttlb = time.perf_counter() - self.start_time
            self.request_handler(Request(str(e.request_info.url), elapsed, elapsed, e))
            raise
        else:
            self.url = super()._resp.url
            self.ttfb = time.perf_counter() - self.start_time
            await self._resp.read()
            self.ttlb = time.perf_counter() - self.start_time
        return LocustResponse.wrap_response(self._resp)

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await super().__aexit__(exc_type, exc_val, exc_tb)
        if self._resp.error is None:  # no explicit value set in with-block
            self._resp.error = exc_val or self._resp.status >= 400
        self.request_handler(
            Request(
                str(self.url),
                self.ttfb,
                self.ttlb,
                self._resp.error,
            )
        )


class LocustClientSession(ClientSession):
    def __init__(self, request_handler: Callable, runner: Runner | None = None, base_url=None, **kwargs):
        super().__init__(base_url=base_url, **kwargs)
        self.runner = runner
        self._request_handler = request_handler

    # explicitly declare this to get the correct return type and enter session
    async def __aenter__(self) -> LocustClientSession:
        return self

    def get(self, url, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(self._request_handler, super().get(url, **kwargs))

    def post(self, url, **kwargs) -> LocustRequestContextManager:
        return LocustRequestContextManager(self._request_handler, super().post(url, **kwargs))
