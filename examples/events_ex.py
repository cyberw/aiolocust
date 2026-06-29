import threading

from aiolocust import HttpUser, events
from aiolocust.datatypes import Request


class MyUser(HttpUser):
    async def run(self):
        async with self.client.get("http://localhost:8080/") as resp:
            pass


def to_stdout(request: Request) -> None:
    print(f"Request: {request.name}, TTLB: {request.ttlb:.3f}s, Error: {request.error}")


lock = threading.Lock()
f = open("requests.csv", "a", buffering=1)


def to_csv(request: Request) -> None:
    with lock:
        f.write(f"{request.name},{request.ttlb:.3f},{request.error}\n")


events.request.add_listener(to_stdout)
events.request.add_listener(to_csv)
