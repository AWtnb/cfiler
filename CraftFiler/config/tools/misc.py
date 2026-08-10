import os
import subprocess
from pathlib import Path

import ckit  # type: ignore

from . import cpane, kiritori
from .common import DESKTOP_PATH, open_vscode, run_ps1, shell_exec, smart_check_path


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window
    cpane.setup(window)
    kiritori.setup(window)


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
