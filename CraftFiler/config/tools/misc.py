from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterator

import cfiler_msgbox  # type: ignore
import ckit  # type: ignore
import pyauto  # type: ignore

from . import cpane, kiritori
from .common import (
    DESKTOP_PATH,
    get_now,
    open_vscode,
    run_ps1,
    shell_exec,
    smart_check_path,
)


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window
    cpane.setup(window)
    kiritori.setup(window)


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


def git_init() -> None:
    pane = cpane.CPane()
    path = pane.currentPath
    git_path = os.path.join(path, ".git")
    if smart_check_path(git_path):
        kiritori.log(f"'{git_path}' already exists.")
        return
    shell_exec("git", "init", str(path))


def eject_current_drive() -> None:
    pane = cpane.CPane()
    current = pane.currentPath
    if current.startswith("C:"):
        return

    current_drive = Path(current).drive
    other = cpane.CPane(False)
    if other.currentPath.startswith(current_drive):
        other.openPath(DESKTOP_PATH)

    pane.openPath(DESKTOP_PATH)

    def _eject(job_item: ckit.JobItem) -> None:
        job_item.result = None
        proc = run_ps1("eject", current_drive)
        if proc.returncode != 0:
            if o := proc.stdout:
                kiritori.log(o)
            if e := proc.stderr:
                kiritori.log(e)
            return
        job_item.result = f"Ejected drive '{current_drive}'"

    def _finished(job_item: ckit.JobItem) -> None:
        if job_item.result is None:
            pane.openPath(current)
            kiritori.log(f"Failed to eject drive '{current_drive}'")
        else:
            kiritori.log(job_item.result)

    job = ckit.JobItem(_eject, _finished)
    window.taskEnqueue(job, create_new_queue=False)


def reset_hotkey() -> None:
    window.ini.set("HOTKEY", "activate_vk", "0")
    window.ini.set("HOTKEY", "activate_mod", "0")


def reload_config() -> None:
    window.configure()
    ts = get_now().strftime("%Y-%m-%d %H:%M:%S.%f")
    window.setStatusMessage(f"Reloaded config.py | {ts}", 2000)


def edit_config() -> None:
    config_dir = os.path.join(os.environ.get("APPDATA", ""), "CraftFiler")
    if not smart_check_path(config_dir):
        kiritori.log(f"cannot find config dir: {config_dir}")
        return
    dir_path = config_dir
    if (real_path := os.path.realpath(config_dir)) != config_dir:
        dir_path = os.path.dirname(real_path)

    result = open_vscode(dir_path)
    if not result:
        subprocess.run(["explorer.exe", dir_path], check=False)


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


def toggle_hidden() -> None:
    window.showHiddenFile(not window.isHiddenFileVisible())


def on_vscode() -> None:
    pane = cpane.CPane()
    open_vscode(pane.currentPath)


def duplicate_pane() -> None:
    window.command_ChdirInactivePaneToOther(None)
    pane = cpane.CPane()
    pane.focusOther()


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


def open_desktop_to_other() -> None:
    pane = cpane.CPane()
    other = cpane.CPane(False)
    if DESKTOP_PATH not in [pane.currentPath, other.currentPath]:
        other.openPath(DESKTOP_PATH)
    pane.focusOther()


def starting_position(both_pane: bool = False) -> None:
    window.command_MoveSeparatorCenter(None)
    pane = cpane.CPane()
    if pane.currentPath != DESKTOP_PATH:
        pane.openPath(DESKTOP_PATH)
    if both_pane:
        window.command_ChdirInactivePaneToOther(None)
        cpane.LeftPane().activate()


def traverse_file(root: str) -> Iterator[str]:

    def _is_skippable(dir_name: str) -> bool:
        return dir_name == "node_modules" or dir_name.startswith((".", "__"))

    for dir_path, dir_names, file_names in os.walk(root):
        dir_names[:] = [d for d in dir_names if not _is_skippable(d)]
        for f in file_names:
            yield os.path.join(dir_path, f)


def summarize_for_llm(root: Path, targets: list[str]) -> tuple[str, int]:
    paths = []
    for path in targets:
        if Path(path).is_dir():
            paths.extend(traverse_file(path))
        else:
            paths.append(path)

    codeblock = "```"
    lines: list[str] = ["## dir tree\n", codeblock]
    lines.extend(str(Path(p).relative_to(root)) for p in paths)
    lines.append(codeblock)
    lines.append("\n## file contents\n")

    counter = 0
    for path in paths:
        p = Path(path)
        try:
            content = p.read_text(encoding="utf-8")
            counter += 1
        except Exception:  # noqa: BLE001, S112
            continue
        lines.append(f"### {p.relative_to(root)}\n")
        lines.append(f"{codeblock}{p.name}")
        lines.append(content)
        lines.append(f"{codeblock}\n")

    return "\n".join(lines), counter


def make_summary_for_llm_on_other_pane() -> None:
    pane = cpane.CPane()
    root = Path(pane.currentPath)
    summary, item_count = summarize_for_llm(root, pane.selectedItemPaths)
    if item_count < 1:
        return

    summary_name = window.commandLine(
        title="SummaryName (on other pane)", text=f"summary_{root.name}.txt"
    )
    other_pane = cpane.CPane(False)
    Path(other_pane.currentPath, summary_name).write_text(summary, encoding="utf-8")

    kiritori.log(f"Summarized {item_count} items.")
