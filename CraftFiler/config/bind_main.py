from __future__ import annotations

from cfiler import *  # type: ignore

from .tools import cpane, enter, keybinder


def setup(window) -> None:

    cpane.setup(window)
    enter.setup(window)
    keybinder.setup(window)

    for key in [
        "Q",
        "Colon",
        "S-Colon",
        "Period",
        "S-Period",
        "BackSlash",
    ]:
        window.keymap[key] = lambda _: None

    keymap = {
        "L": window.command_Enter,
        "Right": window.command_Enter,
        "S-Enter": window.command_View,
        "C-S-Q": window.command_CancelTask,
        "C-Comma": window.command_ConfigMenu,
        "C-S-Comma": window.command_ConfigMenu2,
        "C-H": window.command_JumpHistory,
        "C-Z": window.command_JumpHistory,
        "Back": window.command_JumpHistory,
        "C-D": window.command_Delete,
        "P": window.command_FocusOther,
        "C-Right": window.command_FocusOther,
        "O": window.command_ChdirActivePaneToOther,
        "S-O": window.command_ChdirInactivePaneToOther,
        "A": window.command_CursorTop,
        "E": window.command_CursorBottom,
        "Home": window.command_CursorTop,
        "End": window.command_CursorBottom,
        "C-S-P": window.command_CommandLine,
        "H": window.command_GotoParentDir,
        "Left": window.command_GotoParentDir,
        "S-F10": window.command_ContextMenu,
        "A-S-F10": window.command_ContextMenuDir,
        "Apps": window.command_ContextMenu,
        "S-Apps": window.command_ContextMenuDir,
        "OpenBracket": window.command_MoveSeparatorLeft,
        "CloseBracket": window.command_MoveSeparatorRight,
        "Yen": window.command_MoveSeparatorCenter,
        "A-S": window.command_SetSorter,
        "S-J": window.command_LogDown,
        "S-K": window.command_LogUp,
        "S-OpenBracket": window.command_MoveSeparatorUp,
        "S-CloseBracket": window.command_MoveSeparatorDown,
        "C-S-R": window.command_BatchRename,
    }

    for key, func in keymap.items():
        window.keymap[key] = func

    keybinder.bind(cpane.adjust_pane_width, "C-S")
    keybinder.bind(cpane.swap_pane, "S")
    keybinder.bind(lambda: cpane.CPane().focusOther(), "C-L")

    keybinder.bind(enter.open_with_smooth_csv, "Comma")
    keybinder.bind(enter.open_with, "C-O")
