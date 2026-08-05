from __future__ import annotations

import os
import shutil
import subprocess
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from pathlib import Path
from typing import Callable

import cfiler_mainwindow  # type: ignore
import ckit  # type: ignore
from cfiler import *  # type: ignore


class PaintOption(Enum):
    LeftLocation = cfiler_mainwindow.PAINT_LEFT_LOCATION
    LeftHeader = cfiler_mainwindow.PAINT_LEFT_HEADER
    LeftItems = cfiler_mainwindow.PAINT_LEFT_ITEMS
    LeftFooter = cfiler_mainwindow.PAINT_LEFT_FOOTER
    RightLocation = cfiler_mainwindow.PAINT_RIGHT_LOCATION
    RightHeader = cfiler_mainwindow.PAINT_RIGHT_HEADER
    RightItems = cfiler_mainwindow.PAINT_RIGHT_ITEMS
    RightFooter = cfiler_mainwindow.PAINT_RIGHT_FOOTER
    FocusedLocation = cfiler_mainwindow.PAINT_FOCUSED_LOCATION
    FocusedHeader = cfiler_mainwindow.PAINT_FOCUSED_HEADER
    FocusedItems = cfiler_mainwindow.PAINT_FOCUSED_ITEMS
    FocusedFooter = cfiler_mainwindow.PAINT_FOCUSED_FOOTER
    VerticalSeparator = cfiler_mainwindow.PAINT_VERTICAL_SEPARATOR
    Log = cfiler_mainwindow.PAINT_LOG
    StatusBar = cfiler_mainwindow.PAINT_STATUS_BAR
    Left = cfiler_mainwindow.PAINT_LEFT
    Right = cfiler_mainwindow.PAINT_RIGHT
    LeftOrRight = cfiler_mainwindow.PAINT_LEFT | cfiler_mainwindow.PAINT_RIGHT
    Focused = cfiler_mainwindow.PAINT_FOCUSED
    Upper = cfiler_mainwindow.PAINT_UPPER
    All = cfiler_mainwindow.PAINT_ALL


def delay(msec: int = 50) -> None:
    if 0 < msec:
        time.sleep(msec / 1000)


def stringify(x: str | None, trim: bool = True) -> str:
    if x:
        if trim:
            return x.strip()
        return x
    return ""


def is_file_locked(path: Path | str) -> bool:
    try:
        with open(path, "a"):
            return False
    except OSError:
        return True


def smart_check_path(path: str | Path, timeout_sec: float | None = None) -> bool:
    """CASE-INSENSITIVE path check with timeout"""
    p = path if isinstance(path, Path) else Path(path)
    try:
        future = ThreadPoolExecutor(max_workers=1).submit(p.exists)
        return future.result(timeout_sec)
    except Exception:  # noqa: BLE001
        return False


DESKTOP_PATH = os.path.expandvars(r"${USERPROFILE}\Desktop")

CFILER_APPDATA_PATH = os.path.join(ckit.getAppDataPath(), "CraftFiler")


def check_fzf() -> bool:
    return shutil.which("fzf.exe") is not None


def open_vscode(*args: str) -> bool:
    try:
        if code_path := shutil.which("code"):
            cmd = [code_path] + list(args)
            subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW, check=False)
            return True
        return False
    except Exception as e:  # noqa: BLE001
        print(e)
        return False


def resolve_scoop_shim(path: str) -> str:
    if r"scoop\shims" in path and path.lower().endswith(".exe"):
        real = str(
            Path(path)
            .with_suffix(".shim")
            .read_text()
            .strip()
            .split(" = ")[-1]
            .replace('"', "")
        )
        return real
    return path


def shell_exec(path: str, *args) -> None:
    if not isinstance(path, str):
        path = str(path)
    if path.startswith("http"):
        webbrowser.open(path)
        return
    path = os.path.expandvars(path)
    try:
        cmd = ["start", "", path] + list(args)
        subprocess.run(cmd, shell=True, check=False)
    except Exception as e:  # noqa: BLE001
        print(e)


def run_ps1(name: str, *args: str):
    ps1 = os.path.join(CFILER_APPDATA_PATH, "powershell", f"{name}.ps1")
    cmd = f'PowerShell -NoProfile -ExecutionPolicy Bypass -File "{ps1}"'
    for a in args:
        cmd += f' "{a}"'
    return subprocess.run(
        cmd, creationflags=subprocess.CREATE_NO_WINDOW, shell=True, check=False
    )


CallbackFunc = Callable[[], None]
