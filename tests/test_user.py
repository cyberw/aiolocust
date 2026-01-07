import pytest
from aiohttp.client_exceptions import ClientResponseError

from aiolocust import LocustClientSession


@pytest.mark.asyncio
async def test_get(httpserver):
    httpserver.expect_request("/").respond_with_data("")

    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/")) as resp:
            assert resp.status == 200

    async with LocustClientSession() as client:
        await _(client)


@pytest.mark.asyncio
async def test_post(httpserver):
    httpserver.expect_request("/", method="POST").respond_with_data("")

    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/")) as resp:
            assert resp.status == 200

    async with LocustClientSession() as client:
        await _(client)


@pytest.mark.asyncio
async def test_raise_for_status(httpserver):
    httpserver.expect_request("/README2.md").respond_with_data("", status=404)

    async def _(client: LocustClientSession):
        async with client.get(httpserver.url_for("/README2.md"), raise_for_status=True) as resp:
            pass

    with pytest.raises(ClientResponseError):
        async with LocustClientSession() as client:
            await _(client)
