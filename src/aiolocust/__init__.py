from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING


class User(ABC):
    def __init__(self, runner: Runner | None = None, **kwargs):
        self.runner: Runner = runner  # pyright: ignore[reportAttributeAccessIssue] # always set outside of unit testing
        self.running = True

    @abstractmethod
    async def run(self): ...

    @asynccontextmanager
    async def cm(self):
        """Override this method if you need an async context manager around the run method"""
        yield


if TYPE_CHECKING:
    from aiolocust.runner import Runner
    from aiolocust.users.http import HttpUser, LocustClientSession


def __getattr__(name):
    # prevent early load of these classes, because they in turn might trigger otel setup
    if name == "HttpUser":
        from aiolocust.users.http import HttpUser

        return HttpUser
    elif name == "LocustClientSession":
        from aiolocust.users.http import LocustClientSession

        return LocustClientSession
    elif name == "Runner":
        from aiolocust.runner import Runner

        return Runner

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["User", "HttpUser", "LocustClientSession", "Runner"]
