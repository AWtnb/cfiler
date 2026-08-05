from __future__ import annotations

from pathlib import Path

from cfiler import *  # type: ignore

from . import archiver
from .archiver import extract_archives, is_extractable, peek_archive
from .cpane import CPane
from .listwindow import invoke_listwindow
from .office import preview_openxml_content


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    archiver.setup(window)


def hook_enter() -> bool:
    pane = CPane()
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
        extract_archives()
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

    if is_extractable(ext):
        peek_archive(focus_path)
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
        result, _ = invoke_listwindow("OpenXML file:", menu)
        if result != -1:
            if result == 0:
                preview_openxml_content(focus_path)
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
