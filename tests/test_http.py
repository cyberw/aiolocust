from unittest.mock import MagicMock

import pytest
import pytest_aiohttp
from aiohttp import ClientConnectorError, WSMsgType, web
from aiohttp.client_exceptions import ClientResponseError
from pytest_httpserver import HTTPServer
from pytest_mock.plugin import MockerFixture

import aiolocust.stats
from aiolocust.datatypes import Request
from aiolocust.http import LocustClientSession


async def test_basic(httpserver: HTTPServer):
    httpserver.expect_request("/").respond_with_data("")

    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/")) as resp:
            assert resp.status == 200
        async with client.post(httpserver.url_for("/")) as resp:
            assert resp.status == 200

    async with LocustClientSession() as client:
        await _(client)


async def test_name(httpserver: HTTPServer, mocker: MockerFixture):
    httpserver.expect_request("/").respond_with_data("")
    mocker.patch("aiolocust.stats.request")

    async def _(client: LocustClientSession):
        assert isinstance(aiolocust.stats.request, MagicMock)  # for type hinting
        async with client.get(httpserver.url_for("/"), name="foo") as resp:
            pass
        r = aiolocust.stats.request.call_args.args[0]
        assert r.url == "foo"

        async with client.get(httpserver.url_for("/doesnt_exist"), name="foo") as resp:
            pass
        r = aiolocust.stats.request.call_args.args[0]
        assert r.url == "foo"
        assert isinstance(r.error, ClientResponseError)

    async with LocustClientSession() as client:
        await _(client)


async def test_hard_fails_raise_and_log(mocker: MockerFixture):
    mocker.patch("aiolocust.stats.request")

    async def _(client: LocustClientSession):
        with pytest.raises(ClientConnectorError):
            async with client.get("http://localhost:6666") as resp:
                raise Exception("This will never be reached")

    async with LocustClientSession() as client:
        await _(client)

    assert isinstance(aiolocust.stats.request, MagicMock)  # for type hinting
    r = aiolocust.stats.request.call_args.args[0]
    assert isinstance(r.error, ClientConnectorError)


async def test_404(httpserver: HTTPServer, mocker: MockerFixture):
    httpserver.expect_request("/").respond_with_data("", 404)
    mocker.patch("aiolocust.stats.request")

    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/")) as resp:
            pass
        assert isinstance(aiolocust.stats.request, MagicMock)  # for type hinting
        r = aiolocust.stats.request.call_args.args[0]
        assert r.url.endswith("/")
        assert isinstance(r.error, ClientResponseError)
        assert "404," in str(r.error)

    async with LocustClientSession() as client:
        await _(client)


async def test_raise_for_status(httpserver: HTTPServer, mocker: MockerFixture):
    mocker.patch("aiolocust.stats.request")

    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/doesnt_exist"), raise_for_status=True) as resp:
            pass
        async with client.get(httpserver.url_for("/this_wont_be_reached")) as resp:
            pass

    async with LocustClientSession() as client:
        with pytest.raises(ClientResponseError):
            await _(client)

    assert isinstance(aiolocust.stats.request, MagicMock)  # for type hinting
    r = aiolocust.stats.request.call_args.args[0]
    assert r.url.endswith("/doesnt_exist")
    assert isinstance(r.error, ClientResponseError)


async def test_assert(httpserver: HTTPServer, mocker: MockerFixture):
    mocker.patch("aiolocust.stats.request")

    async def _(client: LocustClientSession):
        async with client.post(httpserver.url_for("/doesnt_exist")) as resp:
            assert resp.status == 200, "Intentionally failed assert"

    with pytest.raises(AssertionError, match="Intentionally failed assert"):
        async with LocustClientSession() as client:
            await _(client)

    assert isinstance(aiolocust.stats.request, MagicMock)  # for type hinting
    r = aiolocust.stats.request.call_args.args[0]
    assert isinstance(r.error, AssertionError)  # assertion error overwrites the HTTP 500 error


async def test_handler(httpserver: HTTPServer, mocker: MockerFixture):
    httpserver.expect_request("/").respond_with_data("")
    mocker.patch("aiolocust.stats.request")

    async def _(client: LocustClientSession):
        assert isinstance(aiolocust.stats.request, MagicMock)  # for type hinting

        async with client.get(httpserver.url_for("/")) as resp:
            pass
        aiolocust.stats.request.assert_called_once()
        r = aiolocust.stats.request.call_args.args[0]
        assert isinstance(r, Request)  # mainly for type hinting, so we only do this once
        assert r.error is None

        async with client.get(httpserver.url_for("/doesnt_exist")) as resp:
            pass
        r = aiolocust.stats.request.call_args.args[0]
        assert r.error.status == 500  # type: ignore

        # Explicitly mark the request as successful
        async with client.get(httpserver.url_for("/doesnt_exist")) as resp:
            resp.error = False
        r = aiolocust.stats.request.call_args.args[0]
        assert r.error is False

        # Explicit error logs the request as failed, but flow continues
        async with client.get(httpserver.url_for("/")) as resp:
            text = await resp.text()
            if not text.startswith("Hello"):
                resp.error = "Response did not start with 'Hello'"
        r = aiolocust.stats.request.call_args.args[0]
        assert r.error == "Response did not start with 'Hello'"

    async with LocustClientSession() as client:
        await _(client)

    # assert len(requests) == 5
    # assert not requests[0].error
    # assert requests[1].error  # bad response code => error = True
    # assert not requests[2].error  # error explicitly set to False
    # assert requests[3].error == "Response did not start with 'Hello'"
    # assert isinstance(requests[4].error, AssertionError)  # assertion failure overwrites bad response code


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

    async def _(client: LocustClientSession):
        async with client.ws_connect(test_client.make_url("/ws")) as ws:
            await ws.send_str("foo")
            aiolocust.stats.request(Request("send foo", 0, 0, None))
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    aiolocust.stats.request(Request(f"recv {msg.data}", 0, 0, None))
                    await ws.send_str("close")
                elif msg.type == WSMsgType.ERROR:
                    aiolocust.stats.request(Request(f"recv {msg.data}", 0, 0, Exception("error-response")))
                    break

    async with LocustClientSession() as client:
        await _(client)
