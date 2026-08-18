from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import ckit  # type: ignore
from cfiler_resultwindow import popResultWindow  # type: ignore

from . import cpane, kiritori
from .common import get_now, stringify


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    kiritori.setup(window)
    cpane.setup(window)


def is_target(ext: str) -> bool:
    for archiver in window.archiver_list:
        for pattern in archiver[0].split():
            if ext == pattern[1:]:
                return True
    return False


def peek(path: str) -> None:
    p = Path(path)
    archiver = window.getArchiver(p.name)
    if not archiver:
        return

    def _peek(job_item: ckit.JobItem) -> None:
        job_item.name = p.name
        job_item.tree = []

        arc = archiver.openArchive(window.getHWND(), path, 0)
        try:
            for info in arc.iterItems("*"):
                job_item.tree.append(info[0])
        finally:
            arc.close()

    def _finished(job_item: ckit.JobItem) -> None:
        lines = [t for t in job_item.tree]
        popResultWindow(window, f"[Peek] {job_item.name}", "\n".join(lines))

    job = ckit.JobItem(_peek, _finished)
    window.taskEnqueue(job, create_new_queue=False)


def extract_with_7zip(dest: str, *paths: str) -> None:
    seven_zip = shutil.which("7z")
    if seven_zip is None:
        kiritori.log("7z not found.")
        return

    targets = [t for t in paths if Path(t).is_file() and is_target(Path(t).suffix)]
    if len(targets) < 1:
        return

    def _extract(_) -> None:
        kiritori.draw_header(f"Extracting as '{dest}'...")

        for target in targets:
            try:
                cmd = [
                    seven_zip,
                    "x",
                    target,
                    f"-o{dest}",
                    "-y",
                ]
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False,
                )
                if proc.returncode != 0:
                    if o := proc.stdout:
                        kiritori.log(o)
                    if e := proc.stderr:
                        kiritori.log(e)
            except Exception as e:  # noqa: BLE001
                kiritori.log(e)
                return

    def _finished(_) -> None:
        print("Finished")
        kiritori.draw_footer()
        pane = cpane.CPane()
        pane.refresh()
        pane.focusByName(Path(dest).name)

    job = ckit.JobItem(_extract, _finished)
    window.taskEnqueue(job, create_new_queue=False)


def extract() -> None:
    pane = cpane.CPane()

    for item in pane.selectedItems:
        ext = Path(item.getFullpath()).suffix
        if not is_target(ext):
            pane.unSelectByName(item.getName())

    if not pane.hasSelection:
        return

    placeholder = (
        Path(pane.selectedItemPaths[0]).stem
        if len(pane.selectedItems) == 1
        else f"extract_{get_now().strftime('%Y%m%d-%H%M%S')}"
    )

    result = stringify(
        window.commandLine(
            "Extract as",
            text=placeholder,
        )
    )
    if len(result) < 1:
        return

    if pane.byName(result) != -1:
        kiritori.log(f"'{result}' already exists.")
        return

    extract_path = os.path.join(pane.currentPath, result)

    if shutil.which("7z") is not None:
        extract_with_7zip(extract_path, *pane.selectedItemPaths)
    else:
        pane.adjustWidth()
        cpane.CPane(False).openPath(extract_path)
        window.command_ExtractArchive(None)


def compress_with_7zip(zip_path: str, *targets: str) -> None:
    seven_zip = shutil.which("7z")
    if seven_zip is None:
        kiritori.log("7z not found.")
        return

    def _compress(_) -> None:
        try:
            cmd = [seven_zip, "a", "-tzip", "-y", zip_path] + list(targets)
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
            if proc.returncode != 0:
                if o := proc.stdout:
                    kiritori.log(o)
                if e := proc.stderr:
                    kiritori.log(e)
        except Exception as e:  # noqa: BLE001
            kiritori.log(e)
            return

    def _finished(_) -> None:
        pass

    job = ckit.JobItem(_compress, _finished)
    window.taskEnqueue(job, create_new_queue=False)


def compress() -> None:
    pane = cpane.CPane()
    targets = pane.selectedItemPaths

    if len(targets) < 1:
        return

    placeholder = get_now().strftime("%Y%m%d-%H%M%S")
    if len(targets) == 1:
        placeholder = Path(targets[0]).name

    result = stringify(window.commandLine("Zip name", text=placeholder))
    if len(result) < 1:
        return
    if not result.endswith(".zip"):
        result += ".zip"

    if pane.byName(result) != -1:
        kiritori.log(f"'{result}' already exists.")
        return

    zip_path = os.path.join(pane.currentPath, result)

    if shutil.which("7z") is not None:
        compress_with_7zip(zip_path, *targets)
    else:
        pane.adjustWidth()
        window.command_CreateArchive(None)
