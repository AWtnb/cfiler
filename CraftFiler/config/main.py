from __future__ import annotations

import ckit  # type: ignore
from cfiler import *  # type: ignore

from .tools import (
    change_dir,
    clipboard,
    clon,
    cpane,
    enter,
    item_filter,
    item_handler,
    keybinder,
    kiritori,
    misc,
    selector,
    snapper,
)
from .tools.rename import affix_handler, renamer
from .tools.rename import extension as rename_ext
from .tools.rename import index as rename_index
from .tools.rename import ini as rename_ini
from .tools.rename import insert as rename_insert
from .tools.rename import photo as rename_photo
from .tools.rename import pseudo_voising as rename_pseudo_voicing
from .tools.rename import regexp as rename_regexp
from .tools.rename import stem as rename_stem
from .tools.rename import substr as rename_substr


def setup(window) -> None:

    affix_handler.setup(window)
    change_dir.setup(window)
    clipboard.setup(window)
    clon.setup(window)
    cpane.setup(window)
    enter.setup(window)
    item_filter.setup(window)
    item_handler.setup(window)
    keybinder.setup(window)
    kiritori.setup(window)
    misc.setup(window)
    rename_ext.setup(window)
    rename_index.setup(window)
    rename_ini.setup(window)
    rename_insert.setup(window)
    rename_photo.setup(window)
    rename_pseudo_voicing.setup(window)
    rename_regexp.setup(window)
    rename_stem.setup(window)
    rename_substr.setup(window)
    renamer.setup(window)
    selector.setup(window)
    snapper.setup(window)

    ckit.CronTable.defaultCronTable().add(clon.invoke_tempfile_cleaner())
    window.enter_hook = enter.hook_enter

    def reset_default_keys(keys: list) -> None:
        for key in keys:
            window.keymap[key] = lambda _: None

    reset_default_keys(
        [
            "Q",
            "Colon",
            "S-Colon",
            "Period",
            "S-Period",
            "BackSlash",
        ]
    )

    def apply_cfiler_command(mapping: dict) -> None:
        for key, func in mapping.items():
            window.keymap[key] = func

    apply_cfiler_command(
        {
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
    )

    def bind_selector() -> None:
        for k, v in {
            "C-A": selector.all_items,
            "U": selector.clear_all,
            "Esc": selector.clear_all,
            "A-F": selector.files,
            "A-D": selector.dirs,
            "S-Home": selector.to_top,
            "S-A": selector.to_top,
            "S-End": selector.to_bottom,
            "S-E": selector.to_bottom,
        }.items():
            keybinder.bind(v, k)

    bind_selector()

    keybinder.bind(change_dir.change_drive, "D")
    keybinder.bind(change_dir.go_to, "C-G")
    keybinder.bind(change_dir.open_latest_under_tree, "S-A-N")
    keybinder.bind(change_dir.to_ghq_repo, "G")
    keybinder.bind(change_dir.zyw.invoke(skip_file=False), "S-Z")
    keybinder.bind(change_dir.zyw.invoke(skip_file=True), "Z")
    keybinder.bind(clipboard.copy_current_path, "C-A-P")
    keybinder.bind(clipboard.hook_copy, "C-C")
    keybinder.bind(clipboard.hook_paste, "C-V", "S-Insert")
    keybinder.bind(cpane.adjust_pane_width, "C-S")
    keybinder.bind(cpane.swap_pane, "S")
    keybinder.bind(enter.open_with_smooth_csv, "Comma")
    keybinder.bind(enter.open_with, "C-O")
    keybinder.bind(item_filter.clear_filter, "Q")
    keybinder.bind(item_filter.hide_unselected, "S-H")
    keybinder.bind(item_handler.duplicate_with_new_extension, "A-S-D")
    keybinder.bind(item_handler.duplicate_with_new_stem, "S-D")
    keybinder.bind(item_handler.open_on_explorer, "C-S-E")
    keybinder.bind(item_handler.open_parent_to_other, "S-U")
    keybinder.bind(item_handler.open_to_other, "S-L")
    keybinder.bind(item_handler.quick_copy, "C")
    keybinder.bind(item_handler.quick_move, "M")
    keybinder.bind(item_handler.recylcebin, "Delete")
    keybinder.bind(item_handler.smart_mkdir, "C-S-N")
    keybinder.bind(item_handler.touch_new_file, "T")
    keybinder.bind(lambda: cpane.CPane().focusOther(), "C-L")
    keybinder.bind(lambda: item_handler.smart_copy_to_dir(False), "S-C")
    keybinder.bind(lambda: item_handler.smart_copy_to_dir(True), "S-M")
    keybinder.bind(lambda: misc.starting_position(False), "0")
    keybinder.bind(lambda: misc.starting_position(True), "S-0")
    keybinder.bind(lambda: selector.select_regexp(True), "S-Colon")
    keybinder.bind(misc.duplicate_pane, "W")
    keybinder.bind(misc.edit_config, "C-E")
    keybinder.bind(misc.new_cfiler_window, "C-N")
    keybinder.bind(misc.on_vscode, "V")
    keybinder.bind(misc.open_desktop_to_other, "A-O")
    keybinder.bind(misc.open_lazygit, "A-L")
    keybinder.bind(misc.reload_config, "C-R", "F5")
    keybinder.bind(misc.safe_quit, "C-Q", "A-F4")
    keybinder.bind(misc.toggle_hidden, "C-S-H")
    keybinder.bind(rename_ext.execute, "S-N")
    keybinder.bind(rename_index.execute, "A-S-I")
    keybinder.bind(rename_insert.execute, "S-I")
    keybinder.bind(rename_regexp.execute, "S-R")
    keybinder.bind(rename_stem.execute, "N")
    keybinder.bind(rename_substr.execute, "S-S")
    keybinder.bind(selector.select_byext, "S-X")
    keybinder.bind(selector.select_empty_dir, "A-E")
    keybinder.bind(selector.select_stem_contains, "Colon")
    keybinder.bind(selector.select_stem_endswith, "S-4")
    keybinder.bind(selector.select_stem_startswith, "Caret")
    keybinder.bind(selector.unselect_panes, "C-U", "S-Esc")
    keybinder.bind(snapper.to_home_position, "C-0")
    keybinder.bind(window.command_Enter, "L", "Right")
