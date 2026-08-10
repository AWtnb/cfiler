import os
import shutil
from pathlib import Path

import ckit  # type:ignore

from . import cpane, kiritori, listwindow
from .common import get_now, shell_exec, smart_check_path, stringify
from .rename import affix_handler


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    cpane.setup(window)
    listwindow.setup(window)
    kiritori.setup(window)


def quick_move() -> None:
    pane = cpane.CPane()
    if not pane.hasSelection:
        window.command_Select(None)
    pane.adjustWidth()
    window.command_Move(None)


def quick_copy() -> None:
    pane = cpane.CPane()
    if not pane.hasSelection:
        window.command_Select(None)
    pane.adjustWidth()
    window.command_Copy(None)


def recylcebin() -> None:
    shell_exec("shell:RecycleBinFolder")


def open_on_explorer() -> None:
    pane = cpane.CPane(True)
    shell_exec(pane.currentPath)


def open_to_other() -> None:
    pane = cpane.CPane(True)
    if not pane.isBlank:
        cpane.CPane(False).openPath(pane.focusedItemPath)
        pane.focusOther()


def open_parent_to_other() -> None:
    pane = cpane.CPane(True)
    parent, current_name = os.path.split(pane.currentPath)
    cpane.CPane(False).openPath(parent, current_name)
    pane.focusOther()


def duplicate_with_new_stem() -> None:
    pane = cpane.CPane()

    src_path = Path(pane.focusedItemPath)
    if pane.hasSelection:
        if 1 < len(pane.selectedItems):
            kiritori.log("Caneled. (Select nothing or just 1 item)")
            return
        src_path = Path(pane.selectedItemPaths[0])

    sel_end = len(src_path.stem)
    sel_start = src_path.stem.rfind("_")
    if sel_start < 0:
        sel_start = sel_end
    prompt = "NewStem"
    placeholder = src_path.stem
    result = stringify(
        window.commandLine(
            title=prompt,
            text=placeholder,
            candidate_handler=affix_handler.invoke_suffix_handler(),
            selection=[sel_start, sel_end],
        )
    )

    if len(result) < 1:
        return

    if src_path.is_file():
        result = result + src_path.suffix
    new_path = src_path.with_name(result)

    if smart_check_path(new_path):
        kiritori.log("Canceled. (Same item exists)")
        return

    def _copy_as(new_path: str) -> None:
        if src_path.is_dir():
            shutil.copytree(src_path, new_path)
        else:
            shutil.copy(src_path, new_path)

    window.subThreadCall(_copy_as, (new_path,))
    pane.refresh()
    pane.focusByName(new_path.name)


def duplicate_with_new_extension() -> None:
    pane = cpane.CPane()

    src_path = Path(pane.focusedItemPath)
    if pane.hasSelection:
        if 1 < len(pane.selectedItems):
            kiritori.log("Caneled. (Select nothing or just 1 item)")
            return
        src_path = Path(pane.selectedItemPaths[0])

    if src_path.is_dir():
        kiritori.log("Caneled. (Dirctory has no extension)")
        return

    sel_start = len(src_path.stem) + 1
    sel_end = len(src_path.name)
    prompt = "NewName"
    result = stringify(
        window.commandLine(
            title=prompt,
            text=src_path.name,
            selection=[sel_start, sel_end],
        )
    )

    if len(result) < 1:
        return

    new_path = src_path.with_name(result)

    if smart_check_path(new_path):
        kiritori.log("Canceled. (Same item exists)")
        return

    def _copy_as(new_path: str) -> None:
        shutil.copy(src_path, new_path)

    window.subThreadCall(_copy_as, (new_path,))
    pane.refresh()
    pane.focusByName(new_path.name)


def smart_copy_to_dir(remove_origin: bool) -> None:
    prompt = "MoveTo" if remove_origin else "CopyTo"

    pane = cpane.CPane()

    items = []
    for item in pane.selectedItems:
        if remove_origin and not hasattr(item, "delete"):
            continue
        items.append(item)

    if len(items) < 1:
        pane.select(pane.cursor)
        return

    dests = []
    for item in pane.items:
        if item.isdir() and not item.selected():
            name = item.getName()
            if name not in dests:
                dests.append(name)

    obs_name = "_obsolete"
    if obs_name not in dests:
        dests.append(obs_name)

    def _listup_dests(
        update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
    ) -> tuple:
        found = [
            dest for dest in dests if dest.lower().startswith(update_info.text.lower())
        ]
        return found, 0

    placeholder = "" if len(pane.dirs) != 1 else pane.dirs[0].getName()
    result, mod = window.commandLine(
        prompt,
        text=placeholder,
        candidate_handler=_listup_dests,
        return_modkey=True,
    )

    result = stringify(result)
    if len(result) < 1:
        return

    dir_path = os.path.join(pane.currentPath, result)
    if not smart_check_path(dir_path):
        pane.mkdir(result)
    pane.copyToChild(result, items, remove_origin)
    if mod == ckit.MODKEY_SHIFT:
        pane.openPath(dir_path)
    else:
        pane.focusByName(result)


def smart_mkdir() -> None:
    pane = cpane.CPane()
    ts = get_now().strftime("%Y%m%d")
    result, mod = window.commandLine(
        "DirName",
        text=ts,
        selection=[0, len(ts)],
        candidate_handler=affix_handler.invoke_name_candidate_handler(),
        return_modkey=True,
    )

    dirname = stringify(result)
    if len(dirname) < 1:
        return
    pane.mkdir(dirname)
    if mod == ckit.MODKEY_SHIFT:
        pane.openChild(dirname)


def touch_new_file() -> None:
    pane = cpane.CPane()
    if not hasattr(pane.fileList.getLister(), "touch"):
        return

    result, mod = window.commandLine(
        "Stem",
        candidate_handler=affix_handler.invoke_name_candidate_handler(),
        return_modkey=True,
    )

    stem = stringify(result)
    if len(stem) < 1:
        return

    if "." in stem:
        ext = ""
    else:
        exts = ["txt", "md", "css", "html"]

        def _listup_exts(
            update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
        ) -> tuple:
            found = [
                ext for ext in exts if ext.lower().startswith(update_info.text.lower())
            ]
            return found, 0

        ext = window.commandLine(
            "Extension",
            text=exts[0],
            selection=[0, len(exts[0])],
            candidate_handler=_listup_exts,
            auto_complete=True,
        )

        if ext is None:
            return
        if len(ext) < 1:
            ext = exts[0]
        ext = "." + ext

    new_name = stem + ext
    new_path = os.path.join(pane.currentPath, new_name)
    if smart_check_path(new_path):
        kiritori.log(f"'{stem}' already exists.")
        return

    pane.touch(new_name)
    if mod == ckit.MODKEY_SHIFT:
        shell_exec(new_path)
