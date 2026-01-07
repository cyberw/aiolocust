import pytest
from aiohttp.client_exceptions import ClientResponseError

from aiolocust import LocustClientSession


@pytest.mark.asyncio
async def test_session():
    async def _(client: LocustClientSession):
        async with client.get(
            "https://locust.io/static/img/screenshot_2.31.3-dev_dark.png"
        ) as resp:
            assert resp.status == 200

    async with LocustClientSession() as client:
        await _(client)


@pytest.mark.asyncio
async def test_raise_for_status():
    async def _(client: LocustClientSession):
        async with client.get("http://localhost/README2.md", raise_for_status=True) as resp:
            pass

    with pytest.raises(ClientResponseError):
        async with LocustClientSession() as client:
            await _(client)
