from __future__ import annotations

import inspect
from typing import Callable

import ckit  # type: ignore
from cfiler import *  # type: ignore


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window


def wrap(func: Callable[..., None]) -> Callable[[ckit.ckit_command.CommandInfo], None]:
    if len(inspect.signature(func).parameters) < 1:

        def _callback(_) -> None:
            func()

        return _callback

    return func


def bind(func: Callable[..., None], *keys: str) -> None:
    for key in keys:
        window.keymap[key] = wrap(func)
