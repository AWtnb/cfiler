from __future__ import annotations

from .tools import bookmark, keybinder


def setup(window) -> None:

    bookmark.setup(window)

    keybinder.bind(bookmark.toggle_bookmark, "C-B")
    keybinder.bind(lambda: bookmark.fuzzy_bookmark(False), "B")
    keybinder.bind(lambda: bookmark.fuzzy_bookmark(True), "A-S-B")
