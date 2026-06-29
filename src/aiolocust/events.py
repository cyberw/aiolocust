from collections.abc import Callable
from typing import ParamSpec

from aiolocust.datatypes import Request

P = ParamSpec("P")


class EventHook[**P]:
    def __init__(self):
        self._handlers: list[Callable[P, None]] = []

    def add_listener(self, func: Callable[P, None]) -> Callable[P, None]:
        if func not in self._handlers:
            self._handlers.append(func)
        else:
            pass  # ignore duplicate listener registration
        return func

    def fire(self, *args: P.args, **kwargs: P.kwargs) -> None:
        for handler in self._handlers:
            handler(*args, **kwargs)


class Events:
    def __init__(self):
        self._clear_handlers()

    def _clear_handlers(self):
        self.startup = EventHook[[]]()
        self.request = EventHook[[Request]]()
