from abc import ABC, abstractmethod
from contextlib import asynccontextmanager


class User(ABC):
    def __init__(self, runner: Runner | None = None, **kwargs):
        self.runner = runner

    @abstractmethod
    async def run(self): ...

    @asynccontextmanager
    async def cm(self):
        """Override this method if you need an async context manager around the run method"""
        yield


from aiolocust.http import HttpUser, LocustClientSession  # noqa: F401
from aiolocust.runner import Runner  # noqa: F401
