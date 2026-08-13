from __future__ import annotations

from .tools import clipboard, keybinder


def setup(window) -> None:

    keybinder.setup(window)
    clipboard.setup(window)

    keybinder.bind(clipboard.copy_current_path, "C-A-P")
    keybinder.bind(clipboard.hook_copy, "C-C")
    keybinder.bind(clipboard.hook_paste, "C-V", "S-Insert")
