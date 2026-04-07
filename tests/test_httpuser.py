import asyncio

import aiohttp
import pytest
from pytest_httpserver import HTTPServer

from aiolocust import HttpUser


async def user_loop(user_instance):  # this is basically copied from runner.user_loop()
    async with user_instance.cm():
        await user_instance.run()


async def test_basic(httpserver: HTTPServer):
    httpserver.expect_request("/").respond_with_data("")

    class BasicUser(HttpUser):
        async def run(self):
            async with self.client.get(httpserver.url_for("/")) as resp:
                assert resp.status == 200

    await user_loop(BasicUser())


async def test_kwargs_forwarded_to_session(httpserver: HTTPServer):
    httpserver.expect_request("/").respond_with_data("")

    class TimeoutUser(HttpUser):
        session_kwargs = {"timeout": aiohttp.ClientTimeout(0.0001)}

        async def run(self):
            async with self.client.get(httpserver.url_for("/")) as resp:
                pass

    with pytest.raises(asyncio.TimeoutError):
        await user_loop(TimeoutUser())
