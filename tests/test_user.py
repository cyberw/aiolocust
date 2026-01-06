import pytest

from aiolocust import LocustClientSession


async def example_user(client: LocustClientSession):
    async with client.get("https://locust.io/static/img/screenshot_2.31.3-dev_dark.png") as resp:
        assert resp.status == 200


@pytest.mark.asyncio
async def test_session():
    async with LocustClientSession() as client:
        await example_user(client)
