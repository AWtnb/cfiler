from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Callable

from cfiler import *  # type: ignore

from . import archiver, cpane, listwindow, office
from .browser_info import get_default_browser
from .common import open_vscode, shell_exec, smart_check_path


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    archiver.setup(window)
    cpane.setup(window)
    listwindow.setup(window)
    office.setup(window)


def hook_enter() -> bool:
    pane = cpane.CPane()
    if pane.isBlank:
        pane.focusOther()
        return True

    focus_path = pane.focusedItemPath
    p = Path(focus_path)
    if p.is_dir():
        pane.openPath(focus_path)
        return True

    if (
        pane.focusedItemPath.endswith(".zip")
        and pane.focusedItem.selected()
        and len(pane.selectedItems) == 1
    ):
        archiver.extract()
        return True

    if pane.focusedItem.size() == 0:
        window.command_Execute(None)
        return True

    ext = p.suffix

    if ext in window.image_file_ext_list:
        pane.appendHistory(focus_path, True)
        return False

    if ext in window.music_file_ext_list:
        window.command_Execute(None)
        return True

    if archiver.is_target(ext):
        archiver.peek(focus_path)
        return True

    if ext.lower() in [
        ".docx",
        ".xlsx",
    ]:
        menu = []
        if ext == ".docx":
            menu.append("Peek")
        else:
            menu.append("Peek sheet1")
        menu.append("Open")
        result, _ = listwindow.invoke("OpenXML file:", menu)
        if result != -1:
            if result == 0:
                office.preview_content(focus_path)
            else:
                window.command_Execute(None)
        return True

    if ext[1:].lower() in [
        "tbx",
        "cmx",
        "webp",
        "m4a",
        "mp4",
        "pdf",
        "xls",
        "doc",
        "pptx",
        "ppt",
    ]:
        window.command_Execute(None)
        return True

    return False


def open_with() -> None:
    pane = cpane.CPane()
    if pane.isBlank:
        return

    if any(item.isdir() for item in pane.selectedItems):
        return

    paths = pane.selectedItemPaths
    if len(paths) < 1 and not pane.focusedItem.isdir():
        paths.append(pane.focusedItemPath)

    app_table = {}
    if len({Path(p).suffix for p in paths}) != 1:
        app_table["(associated app)"] = shell_exec

    if any(path.endswith(".pdf") for path in paths):
        sumatra_path = r"C:\Program Files\SumatraPDF\SumatraPDF.exe"
        if smart_check_path(sumatra_path):
            app_table["sumatra"] = sumatra_path

        acrobat_path = r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe"
        if smart_check_path(acrobat_path):
            app_table["adobe"] = acrobat_path
        else:
            acrobat_reader_path = (
                r"C:\Program Files (x86)\Adobe\Acrobat Reader DC\Reader\AcroRd32.exe"
            )
            if smart_check_path(acrobat_reader_path):
                app_table["adobe-reader"] = acrobat_reader_path

        if (xedit_path := shutil.which("pdfxedit")) is not None:
            app_table["xEdit"] = xedit_path

        if (browser_path := get_default_browser()) != "":
            app_table["browser"] = browser_path

    app_table["notepad"] = r"C:\Windows\System32\notepad.exe"
    app_table["mery"] = os.path.expandvars(r"${LOCALAPPDATA}\Programs\Mery\Mery.exe")
    app_table["vscode"] = lambda x: open_vscode(x, "--new-window")

    if all((Path(path).suffix in [".txt", ".csv"]) for path in paths):
        smooth_csv_path = r"C:\Program Files\SmoothCSV\smoothcsv-app.exe"
        if smart_check_path(smooth_csv_path):
            app_table["smooth csv"] = smooth_csv_path

    names = list(app_table.keys())

    result, _ = listwindow.invoke("open with:", names)
    if result < 0:
        return

    exe = app_table[names[result]]
    for path in paths:
        if isinstance(exe, Callable):
            exe(path)  # ty:ignore[call-top-callable]
        else:
            shell_exec(exe, path)
