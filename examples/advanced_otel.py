from aiolocust import HttpUser


async def run(self: HttpUser):
    async with self.client.get("http://localhost:8080/") as resp:
        resp.span.set_attribute("custom.attribute", "example")
