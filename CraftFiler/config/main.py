from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import cfiler_msgbox  # type: ignore
import ckit  # type: ignore
import pyauto  # type: ignore
from cfiler import *  # type: ignore

from .tools import (
    archiver,
    bookmark,
    change_dir,
    clipboard,
    clon,
    compare,
    cpane,
    cursor_jumper,
    cursor_mover,
    enter,
    item_filter,
    item_handler,
    keybinder,
    kiritori,
    linker,
    listwindow,
    misc,
    office,
    selector,
    snapper,
)
from .tools.common import (
    DESKTOP_PATH,
    CallbackFunc,
    get_now,
    open_vscode,
    shell_exec,
    smart_check_path,
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
    archiver.setup(window)
    bookmark.setup(window)
    change_dir.setup(window)
    clipboard.setup(window)
    clon.setup(window)
    compare.setup(window)
    cpane.setup(window)
    cursor_jumper.setup(window)
    cursor_mover.setup(window)
    enter.setup(window)
    item_filter.setup(window)
    item_handler.setup(window)
    keybinder.setup(window)
    kiritori.setup(window)
    linker.setup(window)
    listwindow.setup(window)
    misc.setup(window)
    office.setup(window)

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

    keybinder.bind(bookmark.toggle_bookmark, "C-B")
    keybinder.bind(lambda: bookmark.fuzzy_bookmark(False), "B")
    keybinder.bind(lambda: bookmark.fuzzy_bookmark(True), "A-S-B")

    def new_cfiler_window() -> None:
        exe_path = sys.executable
        if smart_check_path(exe_path):
            slashed = DESKTOP_PATH.replace("\\", "/")
            pyauto.shellExecute(
                None,
                exe_path,
                f' -L"{slashed}" -R"{slashed}"',
            )
        else:
            kiritori.log(f"{exe_path} not found.")

    keybinder.bind(new_cfiler_window, "C-N")

    keybinder.bind(cursor_mover.smart_cursorUp, "K", "Up")
    keybinder.bind(cursor_mover.smart_cursorDown, "J", "Down")
    keybinder.bind(cursor_mover.focus_latest_item, "A-N")

    keybinder.bind(selector.select_empty_dir, "A-E")

    keybinder.bind(change_dir.open_latest_under_tree, "S-A-N")
    keybinder.bind(cursor_mover.focus_by_timestamp, "A-Back", "A-B")

    def open_lazygit() -> None:
        pane = cpane.CPane()
        path = pane.currentPath

        lazygit = "lazygit"
        if shutil.which(lazygit) is None:
            kiritori.log(f"'{lazygit}' not found...")
            return

        git_path = os.path.join(path, ".git")
        if not smart_check_path(git_path):
            kiritori.log(f"'{git_path}' not found.")
            return

        shell_exec("wt.exe", "lazygit", "-p", path)

    keybinder.bind(open_lazygit, "A-L")

    keybinder.bind(cpane.adjust_pane_width, "C-S")

    keybinder.bind(lambda: cpane.CPane().focusOther(), "C-L")

    keybinder.bind(window.command_Enter, "L", "Right")

    def toggle_hidden() -> None:
        window.showHiddenFile(not window.isHiddenFileVisible())

    keybinder.bind(toggle_hidden, "C-S-H")

    keybinder.bind(enter.open_with, "C-O")

    def open_with_smooth_csv(_) -> None:
        smooth_csv_path = r"C:\Program Files\SmoothCSV\smoothcsv-app.exe"
        if not smart_check_path(smooth_csv_path):
            return

        pane = cpane.CPane()
        target = pane.selectedItemPaths
        if len(target) < 1:
            target = [pane.focusedItemPath]

        for p in target:
            if Path(p).suffix in [".csv", ".txt"]:
                shell_exec(smooth_csv_path, p)

    keybinder.bind(open_with_smooth_csv, "Comma")

    keybinder.bind(item_handler.quick_move, "M")

    keybinder.bind(item_handler.quick_copy, "C")

    keybinder.bind(cpane.swap_pane, "S")

    ckit.CronTable.defaultCronTable().add(clon.invoke_tempfile_cleaner())

    keybinder.bind(change_dir.zyw.invoke(skip_file=True), "Z")
    keybinder.bind(change_dir.zyw.invoke(skip_file=False), "S-Z")
    keybinder.bind(cursor_mover.fuzzy_focus, "S-F")

    keybinder.bind(clipboard.hook_paste, "C-V", "S-Insert")
    keybinder.bind(change_dir.change_drive, "D")
    keybinder.bind(change_dir.go_to, "C-G")

    keybinder.bind(change_dir.to_ghq_repo, "G")

    keybinder.bind(item_handler.recylcebin, "Delete")

    keybinder.bind(clipboard.copy_current_path, "C-A-P")

    keybinder.bind(clipboard.hook_copy, "C-C")

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

    keybinder.bind(selector.unselect_panes, "C-U", "S-Esc")

    def smart_jumpDown(by_prefix: bool, selecting: bool) -> CallbackFunc:
        def _jumper() -> None:
            cursor_jumper.CursorJumper(by_prefix).down(selecting)

        return _jumper

    keybinder.bind(smart_jumpDown(True, False), "A-J")
    keybinder.bind(smart_jumpDown(True, True), "S-A-J")
    keybinder.bind(smart_jumpDown(False, False), "C-J")
    keybinder.bind(smart_jumpDown(False, True), "S-C-J")

    def smart_jumpUp(by_prefix: bool, selecting: bool) -> CallbackFunc:
        def _jumper() -> None:
            cursor_jumper.CursorJumper(by_prefix).up(selecting)

        return _jumper

    keybinder.bind(smart_jumpUp(True, False), "A-K")
    keybinder.bind(smart_jumpUp(True, True), "S-A-K")
    keybinder.bind(smart_jumpUp(False, False), "C-K")
    keybinder.bind(smart_jumpUp(False, True), "S-C-K")

    def duplicate_pane() -> None:
        window.command_ChdirInactivePaneToOther(None)
        pane = cpane.CPane()
        pane.focusOther()

    keybinder.bind(duplicate_pane, "W")

    keybinder.bind(item_handler.open_on_explorer, "C-S-E")
    keybinder.bind(item_handler.open_to_other, "S-L")
    keybinder.bind(item_handler.open_parent_to_other, "S-U")

    def on_vscode() -> None:
        pane = cpane.CPane()
        open_vscode(pane.currentPath)

    keybinder.bind(on_vscode, "V")

    keybinder.bind(rename_substr.execute, "S-S")

    keybinder.bind(rename_insert.execute, "S-I")

    keybinder.bind(rename_index.execute, "A-S-I")

    keybinder.bind(rename_regexp.execute, "S-R")

    keybinder.bind(rename_stem.execute, "N")

    keybinder.bind(rename_ext.execute, "S-N")

    keybinder.bind(item_handler.duplicate_with_new_stem, "S-D")

    keybinder.bind(item_handler.duplicate_with_new_extension, "A-S-D")

    keybinder.bind(lambda: item_handler.smart_copy_to_dir(True), "S-M")
    keybinder.bind(lambda: item_handler.smart_copy_to_dir(False), "S-C")

    keybinder.bind(item_handler.smart_mkdir, "C-S-N")

    keybinder.bind(item_handler.touch_new_file, "T")

    keybinder.bind(snapper.to_home_position, "C-0")

    def reload_config() -> None:
        window.configure()
        ts = get_now().strftime("%Y-%m-%d %H:%M:%S.%f")
        window.setStatusMessage(f"Reloaded config.py | {ts}", 2000)

    keybinder.bind(reload_config, "C-R", "F5")

    def open_desktop_to_other() -> None:
        pane = cpane.CPane()
        other = cpane.CPane(False)
        if DESKTOP_PATH not in [pane.currentPath, other.currentPath]:
            other.openPath(DESKTOP_PATH)
        pane.focusOther()

    keybinder.bind(open_desktop_to_other, "A-O")

    def starting_position(both_pane: bool = False) -> None:
        window.command_MoveSeparatorCenter(None)
        pane = cpane.CPane()
        if pane.currentPath != DESKTOP_PATH:
            pane.openPath(DESKTOP_PATH)
        if both_pane:
            window.command_ChdirInactivePaneToOther(None)
            cpane.LeftPane().activate()

    keybinder.bind(lambda: starting_position(False), "0")
    keybinder.bind(lambda: starting_position(True), "S-0")

    def safe_quit() -> None:
        if window.ini.getint("MISC", "confirm_quit"):
            result = cfiler_msgbox.popMessageBox(
                window,
                cfiler_msgbox.MessageBox.TYPE_YESNO,
                "Confirm",
                "Quit?",
            )
            if result != cfiler_msgbox.MessageBox.RESULT_YES:
                return

        left = cpane.LeftPane()
        right = cpane.RightPane()
        for pane in [left, right]:
            if not pane.currentPath.startswith("C:"):
                pane.openPath(DESKTOP_PATH)

        window.quit()

    keybinder.bind(safe_quit, "C-Q", "A-F4")

    keybinder.bind(misc.edit_config, "C-E")

    keybinder.bind(lambda: selector.select_regexp(True), "S-Colon")
    keybinder.bind(selector.select_stem_startswith, "Caret")
    keybinder.bind(selector.select_stem_endswith, "S-4")
    keybinder.bind(selector.select_stem_contains, "Colon")
    keybinder.bind(selector.select_byext, "S-X")

    keybinder.bind(item_filter.hide_unselected, "S-H")

    keybinder.bind(item_filter.clear_filter, "Q")
