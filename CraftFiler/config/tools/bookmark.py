from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import ckit  # type: ignore
from cfiler import *  # type: ignore

from . import cpane, kiritori
from .common import check_fzf, open_vscode, smart_check_path, stringify
from .listwindow import ask_open_by_vscode


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window
    kiritori.setup(window)
    cpane.setup(window)


def okini(*params: str) -> None:
    cli = "okini"
    exe = shutil.which(cli)
    if exe is None:
        kiritori.log(f"{cli} not found.")
        return
    cmd = ["okini"] + list(params)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        encoding="utf-8",
        creationflags=subprocess.CREATE_NO_WINDOW,
        check=False,
    )
    if proc.returncode != 0:
        kiritori.log(proc.stderr)
        return
    return


def get_okini_bookmarks() -> list[dict[str, str]] | None:
    bookmark_json = os.path.expandvars(r"${APPDATA}\okini\bookmarks.json")
    if not smart_check_path(bookmark_json):
        kiritori.log("okini's bookmarks.json not found.")
        return None

    with open(bookmark_json, "r", encoding="utf-8") as f:
        return json.load(f)


def add_bookmark(path: str) -> None:
    window.bookmark.append(path)
    okini("--add", path)
    kiritori.log(f"Bookmarked: '{path}'")


def remove_bookmark(path: str) -> None:
    window.bookmark.remove(path)
    okini("--remove", path)
    kiritori.log(f"Unbookmarked: '{path}'")


def toggle_bookmark() -> None:
    pane = cpane.CPane(True)
    path = pane.focusedItemPath
    dirname, filename = os.path.split(path)
    if filename.lower() in window.bookmark.listDir(dirname):
        remove_bookmark(path)
    else:
        add_bookmark(path)

    pane.refresh()
    pane.repaint()
    other_pane = cpane.CPane(False)
    other_pane.refresh()
    other_pane.repaint()


def bookmark_here() -> None:
    path = cpane.CPane().currentPath
    bookmarks = [p for p in window.bookmark.getItems()]
    if path in bookmarks:
        remove_bookmark(path)
    else:
        add_bookmark(path)


def fuzzy_bookmark(local_only: bool) -> None:
    if not check_fzf():
        kiritori.log("fzf not found.")
        return

    if shutil.which("okini") is None:
        kiritori.log("okini not found.")
        return

    pane = cpane.CPane()

    bookmarks = get_okini_bookmarks()
    if bookmarks is None:
        return

    if local_only:
        pref = pane.currentPath + os.sep
        bookmarks = [bm for bm in bookmarks if bm["path"].startswith(pref)]

    def _select(job_item: ckit.JobItem) -> None:
        job_item.bookmark_name = ""

        names = "\n".join([bm["name"] for bm in bookmarks])
        if names == "":
            return
        cmd = [
            "fzf.exe",
            "--margin=1",
            "--no-color",
            "--input-border=sharp",
            "--layout=reverse",
        ]
        proc = subprocess.run(
            cmd, input=names, capture_output=True, encoding="utf-8", check=False
        )
        if proc.returncode != 0 and (e := proc.stderr):
            kiritori.log(e)
            return
        job_item.bookmark_name = proc.stdout.strip()

    def _open(job_item: ckit.JobItem) -> None:
        name = job_item.bookmark_name
        if name == "":
            return

        path = None
        for bm in bookmarks:
            if bm["name"] == name:
                path = bm["path"]
                break
        if path is None:
            return

        if smart_check_path(os.path.join(path, ".git")) and ask_open_by_vscode():
            open_vscode(path)
            return

        pane.openPath(path)

    job = ckit.JobItem(_select, _open)
    window.taskEnqueue(job, create_new_queue=False)


def set_bookmark_alias() -> None:
    pane = cpane.CPane()
    target = pane.currentPath
    if pane.hasSelection:
        if 1 < len(pane.selectedItems):
            kiritori.log(
                "Canceled. Select just 1 item (or nothing to bookmark current location)."
            )
            return
        target = pane.selectedItemPaths[0]

    placeholder = str(Path(target).name)
    bookmarks = get_okini_bookmarks()
    if bookmarks is not None:
        found: list[str] = []
        for bm in bookmarks:
            if bm["path"] == target:
                found.append(bm["name"])
        if 0 < len(found):
            found.sort(key=len)
            placeholder = "_".join(found)

    alias = stringify(
        window.commandLine("Bookmark alias", text=placeholder, selection=[0, 0])
    )
    if alias == "":
        return

    okini("--add", target, alias)

    if target not in window.bookmark.getItems():
        window.bookmark.append(target)
        if target != pane.currentPath:
            pane.refresh()
    kiritori.log(f"Registered '{alias}' as alias for '{target}'")
