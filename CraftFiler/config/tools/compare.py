from __future__ import annotations

import hashlib
import os
import shutil
import unicodedata
from typing import Iterator

import ckit  # type: ignore

from . import cpane, kiritori
from .common import open_vscode, resolve_scoop_shim, shell_exec
from .protocols import ItemDefaultProtocol


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    kiritori.setup(window)
    cpane.setup(window)


class FileHashDiff:
    def __init__(self, max_mb: int):
        self.max_mb = max_mb

    @staticmethod
    def count_bytes(s: str) -> int:
        n = 0
        for c in s:
            if unicodedata.east_asian_width(c) in "FWA":
                n += 2
            else:
                n += 1
        return n

    def to_hash(self, path: str) -> str:
        mb = 1024 * 1024
        read_size = 1 * mb if self.max_mb * mb < os.path.getsize(path) else None
        with open(path, "rb") as f:
            digest = hashlib.md5(f.read(read_size)).hexdigest()
        return digest

    def progress(self, name: str) -> None:
        print(f"checking first {self.max_mb}MB of: {name}")

    def compare(self) -> None:
        pane = cpane.CPane()
        other_pane = cpane.CPane(False)
        with_selection = other_pane.hasSelection
        _, dirname = os.path.split(pane.currentPath)
        _, other_dirname = os.path.split(other_pane.currentPath)

        def _scan(job_item: ckit.JobItem) -> None:
            targets = []
            for item in pane.selectedOrAllItems:
                pane.unSelectByName(item.getName())
                if not item.isdir():
                    targets.append(item)

            if len(targets) < 1:
                return

            kiritori.draw_header("Comparing md5 hash:")

            window.setProgressValue(None)

            table = {}
            exts = set()

            for file in targets:
                if job_item.isCanceled():
                    return
                path = file.getFullpath()
                digest = self.to_hash(path)
                _, name = os.path.split(path)
                _, ext = os.path.splitext(name)
                self.progress(dirname + os.sep + name)
                table[digest] = table.get(digest, []) + [name]
                exts.add(ext)

            def __files_to_compare() -> (
                Iterator[ItemDefaultProtocol] | list[ItemDefaultProtocol]
            ):
                if with_selection:
                    sels = other_pane.selectedItems
                    other_pane.unSelectAll()
                    return sels
                return other_pane.traverse(True)

            clones: dict[str, list[str]] = {}

            for item in __files_to_compare():
                if job_item.isCanceled():
                    return
                path = item.getFullpath()
                _, ext = os.path.splitext(path)
                if ext not in exts:
                    continue
                rel = os.path.relpath(path, other_pane.currentPath)
                self.progress(other_dirname + os.sep + rel)
                digest = self.to_hash(path)
                if digest in table:
                    names = table[digest]
                    for name in names:
                        clones[name] = clones.get(name, []) + [rel]

            job_item.clones = clones

        def _finish(job_item: ckit.JobItem) -> None:
            window.clearProgress()
            if job_item.isCanceled():
                print("\nCanceled.")
            else:
                print("\nFinished.\n")
                if not job_item.clones or len(job_item.clones) < 1:
                    print("(There was no clone)")
                else:
                    for name, clone_names in job_item.clones.items():
                        pane.selectByName(name)
                        other_pane.selectByNames(
                            [n for n in clone_names if os.sep not in n]
                        )

                        filler = " " * self.count_bytes(name)
                        for i, n in enumerate(clone_names):
                            if i == 0:
                                print(name, "==", n)
                            else:
                                print(filler, "==", n)
                kiritori.draw_footer()

        job = ckit.JobItem(_scan, _finish)
        window.taskEnqueue(job, create_new_queue=False)


def diff_files(with_diffinity: bool) -> None:
    pane = cpane.CPane()
    left_path = ""
    right_path = ""

    if (
        pane.hasSelection
        and len(pane.selectedItems) == 2
        and not cpane.CPane(False).hasSelection
    ):
        left_path, right_path = pane.selectedItemPaths
    else:
        left_pane = cpane.LeftPane()
        right_pane = cpane.RightPane()
        if len(left_pane.selectedItems) == 1 and len(right_pane.selectedItems) == 1:
            left_path = left_pane.selectedItemPaths[0]
            right_path = right_pane.selectedItemPaths[0]

    if not left_path or not right_path:
        kiritori.log("Select 1 item for each pane or 2 items in one pane to compare.")
        return

    if with_diffinity:
        exe_path = shutil.which("Diffinity")
        if exe_path is None:
            kiritori.log("cannnot find diffinity.exe...")
            return

        exe_path = resolve_scoop_shim(exe_path)
        shell_exec(exe_path, left_path, right_path)
        return

    exe_path = shutil.which("code")
    if exe_path is None:
        kiritori.log("cannnot find vscode...")
        return

    def _open_code(_) -> None:
        open_vscode(
            "--new-window",
            "--disable-extensions",
            "--diff",
            left_path,
            right_path,
        )

    job = ckit.JobItem(_open_code, lambda _: None)
    window.taskEnqueue(job, create_new_queue=False)
