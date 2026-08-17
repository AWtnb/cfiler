from __future__ import annotations

from .tools import cursor_jumper, keybinder
from .tools.common import CallbackFunc


def invoke_jumper(downward: bool, by_prefix: bool, selecting: bool) -> CallbackFunc:
    if downward:

        def _jump_down() -> None:
            cursor_jumper.jump_down(by_prefix, selecting)

        return _jump_down

    def _jump_up() -> None:
        cursor_jumper.jump_up(by_prefix, selecting)

    return _jump_up


def setup(window) -> None:

    cursor_jumper.setup(window)
    keybinder.setup(window)

    for (by_prefix, selecting), key in {
        (True, False): "A-J",
        (True, True): "S-A-J",
        (False, False): "C-J",
        (False, True): "S-C-J",
    }.items():
        func = invoke_jumper(True, by_prefix, selecting)
        keybinder.bind(func, key)

    for (by_prefix, selecting), key in {
        (True, False): "A-K",
        (True, True): "S-A-K",
        (False, False): "C-K",
        (False, True): "S-C-K",
    }.items():
        func = invoke_jumper(False, by_prefix, selecting)
        keybinder.bind(func, key)
