from __future__ import annotations

from .tools import item_filter, keybinder


def setup(window) -> None:

    keybinder.setup(window)
    item_filter.setup(window)

    keybinder.bind(item_filter.clear_filter, "Q")
    keybinder.bind(item_filter.hide_unselected, "S-H")
