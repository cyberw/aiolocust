import pytest
import pytest_aiohttp
from aiohttp import ClientConnectorError, WSMsgType, web
from aiohttp.client_exceptions import ClientResponseError
from pytest_httpserver import HTTPServer

from aiolocust.datatypes import Request
from aiolocust.runner import LocustClientSession


async def test_basic(httpserver: HTTPServer):
    httpserver.expect_request("/").respond_with_data("")

    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/")) as resp:
            assert resp.status == 200
        async with client.post(httpserver.url_for("/")) as resp:
            assert resp.status == 200

    def request(req: Request):
        pass

    async with LocustClientSession(request) as client:
        await _(client)


async def test_name(httpserver: HTTPServer):
    httpserver.expect_request("/").respond_with_data("")

    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/"), name="foo") as resp:
            pass
        async with client.get(httpserver.url_for("/doesnt_exist"), name="foo") as resp:
            pass

    requests: list[Request] = []

    def request(req: Request):
        requests.append(req)

    async with LocustClientSession(request_handler=request) as client:
        await _(client)

    assert requests[0].url == "foo"
    assert requests[1].url == "foo"
    assert len(requests) == 2
    assert isinstance(requests[1].error, ClientResponseError)


async def test_hard_fails_raise_and_log():
    async def _(client: LocustClientSession):
        with pytest.raises(ClientConnectorError):
            async with client.get("http://localhost:6666") as resp:
                raise Exception("This will never be reached")

    requests: list[Request] = []

    def request(req: Request):
        requests.append(req)

    async with LocustClientSession(request) as client:
        await _(client)

    assert len(requests) == 1
    assert isinstance(requests[0].error, ClientConnectorError)


async def test_404(httpserver: HTTPServer):
    httpserver.expect_request("/").respond_with_data("", 404)

    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/")) as resp:
            pass
        async with client.get(httpserver.url_for("/")) as resp:
            pass

    requests: list[Request] = []

    def request(req: Request):
        requests.append(req)

    async with LocustClientSession(request_handler=request) as client:
        await _(client)

    assert requests[0].url.endswith("/")
    assert isinstance(requests[0].error, ClientResponseError)
    assert "404," in str(requests[0].error)
    assert len(requests) == 2  # ensure first request failure didnt interrupt flow


async def test_raise_for_status(httpserver: HTTPServer):
    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/doesnt_exist"), raise_for_status=True) as resp:
            pass
        async with client.get(httpserver.url_for("/this_wont_be_reached")) as resp:
            pass

    requests: list[Request] = []

    def request(req: Request):
        requests.append(req)

    async with LocustClientSession(request_handler=request) as client:
        with pytest.raises(ClientResponseError):
            await _(client)

    assert len(requests) == 1
    assert requests[0].url.endswith("doesnt_exist")
    assert isinstance(requests[0].error, ClientResponseError)


async def test_assert(httpserver: HTTPServer):
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

    async with LocustClientSession(request) as client:
        try:
            await _(client)
        except AssertionError:
            pass

    assert len(requests) == 1
    assert isinstance(requests[0].error, AssertionError)


async def test_handler(httpserver: HTTPServer):
    httpserver.expect_request("/", method="GET").respond_with_data("")

    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/")) as resp:
            pass
        # POST is not allowed, will log the request as failed
        async with client.post(httpserver.url_for("/")) as resp:
            pass
        # Explicitly mark the request as successful
        async with client.post(httpserver.url_for("/")) as resp:
            resp.error = False
        # Explicit error logs the request as failed, but flow continues
        async with client.get(httpserver.url_for("/")) as resp:
            text = await resp.text()
            if not text.startswith("Hello"):
                resp.error = "Response did not start with 'Hello'"
        # Assertion failure
        async with client.post(httpserver.url_for("/")) as resp:
            assert resp.status == 200

    requests: list[Request] = []

    def request(req: Request):
        requests.append(req)

    async with LocustClientSession(request) as client:
        try:
            await _(client)
        except AssertionError:
            pass

    assert len(requests) == 5
    assert not requests[0].error
    assert requests[1].error  # bad response code => error = True
    assert not requests[2].error  # error explicitly set to False
    assert requests[3].error == "Response did not start with 'Hello'"
    assert isinstance(requests[4].error, AssertionError)  # assertion failure overwrites bad response code


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            if msg.data == "close":
                await ws.close()
            else:
                await ws.send_str(f"reply-for-{msg.data}")
        elif msg.type == WSMsgType.ERROR:
            print(f"ws connection closed with exception {ws.exception()}")

    return ws


async def test_websocket(aiohttp_client: pytest_aiohttp.AiohttpClient):
    app = web.Application()
    app.add_routes([web.get("/ws", websocket_handler)])
    test_client = await aiohttp_client(app)

    requests: list[Request] = []

    def request(req: Request):
        requests.append(req)

    async def _(client: LocustClientSession):
        async with client.ws_connect(test_client.make_url("/ws")) as ws:
            await ws.send_str("foo")
            request(Request("send foo", 0, 0, None))
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    request(Request(f"recv {msg.data}", 0, 0, None))
                    await ws.send_str("close")
                elif msg.type == WSMsgType.ERROR:
                    request(Request(f"recv {msg.data}", 0, 0, Exception("error-response")))
                    break

    async with LocustClientSession(request) as client:
        await _(client)

    assert requests[0].url == "send foo"
    assert requests[0].error is None
    assert requests[1].url == "recv reply-for-foo"
    assert requests[1].error is None
    assert len(requests) == 2
