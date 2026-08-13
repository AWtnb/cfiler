from __future__ import annotations

from cfiler import *  # type: ignore

from .tools import keybinder, snapper


def setup(window) -> None:

    keybinder.setup(window)
    snapper.setup(window)

    keybinder.bind(snapper.to_home_position, "C-0")
