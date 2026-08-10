from __future__ import annotations

import os
from pathlib import Path

import ckit  # type: ignore
from PIL import ImageGrab  # type: ignore

from . import cpane, kiritori, linker, listwindow, office
from .common import get_now


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window
    cpane.setup(window)
    kiritori.setup(window)
    listwindow.setup(window)
    linker.setup(window)
    office.setup(window)


def copy_dir_tree() -> None:
    pane = cpane.CPane()
    selected_names = pane.selectedItemNames
    root = pane.currentPath
    window.setProgressValue(None)

    def _traverse(job_item: ckit.JobItem) -> None:
        job_item.paths = []
        for item in pane.traverse(False):
            if job_item.isCanceled():
                return
            rel = item.getFullpath()[len(root) :].lstrip(os.sep)
            if len(selected_names) < 1 or any(
                (rel == name or rel.startswith(name + os.sep))
                for name in selected_names
            ):
                job_item.paths.append(rel)

    def _finished(job_item: ckit.JobItem) -> None:
        window.clearProgress()
        if job_item.isCanceled():
            kiritori.log("Canceled.")
        else:
            lines = "\n".join(sorted(job_item.paths))
            ckit.setClipboardText(lines)
            kiritori.log(f"Copied tree: {root}")

    job = ckit.JobItem(_traverse, _finished)
    window.taskEnqueue(job, create_new_queue=False)


def save_clipboard_image_as_file() -> None:
    pane = cpane.CPane()

    def _save(job_item: ckit.JobItem) -> None:
        job_item.file_name = ""
        img = ImageGrab.grabclipboard()
        if not img or isinstance(img, list):
            kiritori.log("Canceled: No image in clipboard.")
            return
        job_item.file_name = get_now().strftime("%Y%m%d-%H%M%S") + ".png"
        save_path = os.path.join(pane.currentPath, job_item.file_name)
        img.save(save_path)

    def _finish(job_item: ckit.JobItem) -> None:
        if job_item.file_name:
            pane.refresh()
            pane.focusByName(job_item.file_name)

    job = ckit.JobItem(_save, _finish)
    window.taskEnqueue(job, create_new_queue=False)


def hook_paste() -> None:
    c = ckit.getClipboardText()
    if len(c) < 1:
        save_clipboard_image_as_file()
        return
    if c.startswith("http"):
        linker.make_internet_shortcut(c)
        return
    cpane.CPane().openPath(c.strip().strip('"'))


def copy_current_path() -> None:
    pane = cpane.CPane()
    p = pane.currentPath
    ckit.setClipboardText(p)
    window.setStatusMessage(f"copied current path: '{p}'", 3000)


def hook_copy() -> None:
    selection_left, selection_right = window.log_pane.selection
    if selection_left != selection_right:
        window.command_SetClipboard_LogSelected(None)
        return

    pane = cpane.CPane()

    targets = []
    if pane.isBlank:
        targets.append(pane.currentPath)
    else:
        targets = pane.selectedItemPaths
        if len(targets) < 1:
            targets.append(pane.focusedItemPath)

    menu = ["Fullpath", "Name"]
    if any(Path(t).is_file() for t in targets):
        menu.append("Basename")

    if all(Path(path).suffix in [".docx", ".xlsx"] for path in targets):
        menu.append("Text content")

    result, _ = listwindow.invoke("Copy", menu)
    if result < 0:
        return

    def _copy(job_item: ckit.JobItem) -> None:
        lines = []
        for target in targets:
            if result == 0:
                lines.append(target)
                continue
            p = Path(target)
            if result == 1:
                lines.append(p.name)
                continue
            if result == 3:
                content = office.read_openxml(target)
                lines.append(content)
                continue
            lines.append(p.stem)
        ckit.setClipboardText("\n".join(lines))
        job_item.count = len(lines)

    def _finished(job_item: ckit.JobItem) -> None:
        s = f"Copied {job_item.count} {menu[result]}"
        if 1 < job_item.count:
            s += "s"
        s += "."
        window.setStatusMessage(s, 2000)

    job = ckit.JobItem(_copy, _finished)
    window.taskEnqueue(job, create_new_queue=False)
