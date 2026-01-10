import pytest
from aiohttp import ClientConnectorError
from aiohttp.client_exceptions import ClientResponseError

from aiolocust import LocustClientSession
from aiolocust.datatypes import Request


@pytest.mark.asyncio
async def test_basic(httpserver):
    httpserver.expect_request("/").respond_with_data("")

    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/")) as resp:
            assert resp.status == 200
        async with client.post(httpserver.url_for("/")) as resp:
            assert resp.status == 200

    async with LocustClientSession() as client:
        await _(client)


@pytest.mark.asyncio
async def test_hard_fails_raise_and_log():
    async def _(client: LocustClientSession):
        with pytest.raises(ClientConnectorError):
            async with client.get("http://localhost:6666") as resp:
                raise Exception("This will never be reached")

    requests: list[Request] = []

    def request(req: Request):
        requests.append(req)

    async with LocustClientSession(request_handler=request) as client:
        await _(client)

    assert len(requests) == 1
    assert requests[0].success is False


@pytest.mark.asyncio
async def test_raise_for_status(httpserver):
    httpserver.expect_request("/README2.md").respond_with_data("", status=404)

    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/README2.md"), raise_for_status=True) as resp:
            pass

    requests: list[Request] = []

    def request(req: Request):
        requests.append(req)

    async with LocustClientSession(None, request_handler=request) as client:
        with pytest.raises(ClientResponseError):
            await _(client)

    assert len(requests) == 1
    assert requests[0].success is False


@pytest.mark.asyncio
async def test_assert(httpserver):
    httpserver.expect_request("/").respond_with_data("")

    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/")) as resp:
            text = await resp.text()
            assert text == "this text isn't there"
        async with client.get(httpserver.url_for("/this_must_not_be_reached")) as resp:
            pass

    requests: list[Request] = []

    def request(req: Request):
        requests.append(req)

    async with LocustClientSession(None, request_handler=request) as client:
        try:
            await _(client)
        except AssertionError:
            pass

    assert len(requests) == 1
    assert requests[0].success is False


@pytest.mark.asyncio
async def test_handler(httpserver):
    httpserver.expect_request("/", method="GET").respond_with_data("")

    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/")) as resp:
            assert resp.status == 200
        # POST is not allowed
        async with client.post(httpserver.url_for("/")) as resp:
            assert resp.status == 200

    requests: list[Request] = []

    def request(req: Request):
        requests.append(req)

    async with LocustClientSession(None, request_handler=request) as client:
        try:
            await _(client)
        except AssertionError:
            pass

    assert len(requests) == 2
    assert requests[0].success is True
    assert requests[1].success is False
