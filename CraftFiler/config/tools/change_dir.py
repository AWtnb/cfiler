from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import ckit  # type: ignore

from . import cpane, kiritori
from .common import (
    DESKTOP_PATH,
    CallbackFunc,
    delay,
    open_vscode,
    smart_check_path,
    stringify,
)
from .listwindow import ask_open_by_vscode, invoke_listwindow


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    kiritori.setup(window)
    cpane.setup(window)


def open_latest_under_tree() -> None:
    pane = cpane.CPane()
    if pane.isBlank:
        return

    root = pane.currentPath

    def _scan(job_item: ckit.JobItem) -> None:
        kiritori.draw_header(f"Searching for newest file under '{root}' ...")
        job_item.latest = None
        for item in pane.traverse(True, "_obsolete"):
            if job_item.latest is None:
                job_item.latest = item
                continue
            if job_item.latest.time() <= item.time():
                job_item.latest = item

    def _open(job_item: ckit.JobItem) -> None:
        if job_item.latest:
            p = job_item.latest.getFullpath()
            pane.openPath(p)
            rel = Path(p).relative_to(Path(root))
            print(f"==> '{rel}'")
        kiritori.draw_footer()

    job = ckit.JobItem(_scan, _open)
    window.taskEnqueue(job, create_new_queue=False)


class zyw:
    exe_name = "zyw.exe"

    @staticmethod
    def get_root(src: str) -> str:
        for path in Path(src).parents:
            p = os.path.join(path, ".root")
            if smart_check_path(p, 0.5):
                return str(path)
        return src

    @classmethod
    def invoke(cls, skip_file: bool) -> CallbackFunc:
        def _wrapper() -> None:
            pane = cpane.CPane()
            if pane.isBlank:
                return

            def __find(job_item: ckit.JobItem) -> None:
                job_item.result = None
                exe_path = shutil.which(cls.exe_name)
                if exe_path is None:
                    kiritori.log(f"Exe not found: '{cls.exe_name}'")
                    return
                root = cls.get_root(pane.currentPath)
                cmd = [
                    exe_path,
                    "-exclude=_obsolete,node_modules",
                    f"-all={not skip_file}",
                    f"-root={root}",
                ]
                delay()
                proc = subprocess.run(
                    cmd, capture_output=True, encoding="utf-8", check=False
                )
                result = proc.stdout.strip()
                if result:
                    if proc.returncode != 0:
                        if result:
                            kiritori.log(result)
                        return
                    job_item.result = result

            def __open(job_item: ckit.JobItem) -> None:
                result = job_item.result
                if result:
                    pane = cpane.CPane()
                    pane.openPath(result)

            job = ckit.JobItem(__find, __open)
            window.taskEnqueue(job, create_new_queue=False)

        return _wrapper


def change_drive() -> None:
    class MenuItem:
        sep = " "

        def __init__(self, drive: str) -> None:
            dn = ckit.getDriveDisplayName(drive)
            detail = dn[: dn.rfind(" ")]
            self.line = drive + self.sep + detail

        @classmethod
        def parse(cls, s: str) -> str:
            return s[: s.find(cls.sep)]

    current_drive = Path(cpane.CPane().currentPath).drive
    menu = []
    for d in ckit.getDrives():
        d += ":"
        if d == current_drive:
            continue
        menu.append(MenuItem(d).line)

    result, mod = invoke_listwindow("Drive", menu, onkeypress="search_and_decide")
    if result < 0:
        return

    drive = MenuItem.parse(menu[result])
    open_path = DESKTOP_PATH if drive == "C:" else f"{drive}\\"
    cpane.CPane(mod != ckit.MODKEY_SHIFT).openPath(open_path)


def go_to() -> None:
    pane = cpane.CPane()

    def _format_sep(s: str) -> str:
        return s.replace("/", os.sep)

    def _listup_names(update_info: ckit.ckit_widget.EditWidget.UpdateInfo) -> tuple:
        t = _format_sep(update_info.text)
        names = pane.names
        if os.sep in t:
            root = pane.currentPath
            names = [
                str(p)[len(root) + 1 :]
                for p in Path(root, t[: t.rfind(os.sep)]).glob("*")
            ]

        found = [
            name for name in names if _format_sep(name).lower().startswith(t.lower())
        ]
        return found, 0

    result = stringify(
        window.commandLine(
            title="GoTo",
            candidate_handler=_listup_names,
            auto_complete=True,
        )
    )

    if result != "":
        pane.openPath(os.path.join(pane.currentPath, result))


def traverse_dir(root: Path, max_depth: int, current_depth: int = 0) -> list[Path]:
    if max_depth <= current_depth:
        return []

    dirs = []
    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        dirs.append(path)
        dirs.extend(traverse_dir(path, max_depth, current_depth + 1))

    return dirs


def to_ghq_repo() -> None:
    ghq_root = os.path.expandvars(r"${USERPROFILE}\ghq")
    if not smart_check_path(ghq_root):
        kiritori.log(f"'{ghq_root}' not found.")
        return

    exe_name = "ghq.exe"
    exe_path = shutil.which(exe_name)
    if exe_path is None:
        kiritori.log(f"cannnot find {exe_name}...")
        return

    def _listup(job_item: ckit.JobItem) -> None:
        job_item.rel_path = None

        root = Path(ghq_root)
        rels = []
        for p in traverse_dir(root, 3):
            rel = str(p.relative_to(root))
            if 1 < rel.count(os.sep):
                rels.append(rel)

        fzf_result = subprocess.run(
            ["fzf"],
            input="\n".join(rels),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )
        if fzf_result.returncode != 0 and (e := fzf_result.stderr):
            kiritori.log(e)
            return

        job_item.rel_path = fzf_result.stdout.strip()

    def _open(job_item: ckit.JobItem) -> None:
        if not job_item.rel_path:
            return

        path = Path(ghq_root) / job_item.rel_path
        if smart_check_path(path / ".git") and ask_open_by_vscode():
            open_vscode(str(path))
            return

        cpane.CPane().openPath(str(path))

    job = ckit.JobItem(_listup, _open)
    window.taskEnqueue(job, create_new_queue=False)
