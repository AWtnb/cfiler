from __future__ import annotations

from .tools import cursor_mover, keybinder


def setup(window) -> None:
    keybinder.setup(window)
    cursor_mover.setup(window)

    keybinder.bind(cursor_mover.smart_cursorUp, "K", "Up")
    keybinder.bind(cursor_mover.smart_cursorDown, "J", "Down")
    keybinder.bind(cursor_mover.focus_latest_item, "A-N")
    keybinder.bind(cursor_mover.fuzzy_focus, "S-F")
    keybinder.bind(cursor_mover.focus_by_timestamp, "A-Back", "A-B")
