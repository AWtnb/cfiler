from __future__ import annotations

from .tools import cursor_jumper, keybinder


def setup(window) -> None:

    cursor_jumper.setup(window)
    keybinder.setup(window)


for (by_prefix, selecting), key in {
    (True, False): "A-J",
    (True, True): "S-A-J",
    (False, False): "C-J",
    (False, True): "S-C-J",
}.items():

    def _jump_down(b=by_prefix, s=selecting) -> None:
        cursor_jumper.CursorJumper(b).down(s)

    keybinder.bind(_jump_down, key)


for (by_prefix, selecting), key in {
    (True, False): "A-K",
    (True, True): "S-A-K",
    (False, False): "C-K",
    (False, True): "S-C-K",
}.items():

    def _jump_up(b=by_prefix, s=selecting) -> None:
        cursor_jumper.CursorJumper(b).up(s)

    keybinder.bind(_jump_up, key)
