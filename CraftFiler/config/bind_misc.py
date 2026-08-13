from __future__ import annotations

from cfiler import *  # type: ignore

from .tools import keybinder, misc


def setup(window) -> None:

    keybinder.setup(window)
    misc.setup(window)

    keybinder.bind(lambda: misc.starting_position(False), "0")
    keybinder.bind(lambda: misc.starting_position(True), "S-0")
    keybinder.bind(misc.duplicate_pane, "W")
    keybinder.bind(misc.edit_config, "C-E")
    keybinder.bind(misc.new_cfiler_window, "C-N")
    keybinder.bind(misc.on_vscode, "V")
    keybinder.bind(misc.open_desktop_to_other, "A-O")
    keybinder.bind(misc.open_lazygit, "A-L")
    keybinder.bind(misc.reload_config, "C-R", "F5")
    keybinder.bind(misc.safe_quit, "C-Q", "A-F4")
    keybinder.bind(misc.toggle_hidden, "C-S-H")
