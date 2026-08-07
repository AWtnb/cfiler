from __future__ import annotations

import re
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

import ckit  # type: ignore

from . import cpane, kiritori
from .common import run_ps1, smart_check_path, stringify


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window
    cpane.setup(window)


def make_junction() -> None:
    active_pane = cpane.CPane()
    if not active_pane.hasSelection:
        return

    other_pane = cpane.CPane(False)
    dest = other_pane.currentPath
    for src_path in active_pane.selectedItemPaths:
        junction_path = Path(dest, Path(src_path).name)
        if smart_check_path(junction_path):
            kiritori.log(f"'{junction_path}' already exists.")
            return
        try:
            cmd = ["cmd", "/c", "mklink", "/J", str(junction_path), src_path]
            proc = subprocess.run(
                cmd, capture_output=True, encoding="cp932", check=False
            )
            result = proc.stdout.strip()
            kiritori.log(result)
        except Exception as e:  # noqa: BLE001
            kiritori.log(e)
            return


def make_internet_shortcut(url: str = "") -> None:
    if not url.startswith("http"):
        kiritori.log(f"invalid url: '{url}'")
        return

    def _access(job_item: ckit.JobItem) -> None:
        job_item.body = None
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as res:
                body = res.read()
                try:
                    text = body.decode("utf-8", errors="ignore")
                except Exception:  # noqa: BLE001
                    text = body.decode("cp932", errors="ignore")
                job_item.body = text
        except Exception as e:  # noqa: BLE001
            kiritori.log(e)

    def _make_shortcut(job_item: ckit.JobItem) -> None:
        title = ""
        if job_item.body is not None:
            m = re.search(
                r"<title.*?>(.*?)</title>", job_item.body, re.IGNORECASE | re.DOTALL
            )
            title = m.group(1).strip() if m else ""

        lines = ["[InternetShortcut]"]
        domain = urllib.parse.urlparse(url).netloc
        name = stringify(
            window.commandLine(
                "Shortcut title",
                text=f"{title} - {domain}",
                selection=[0, len(title)],
            )
        )
        if len(name) < 1:
            print("Canceled.\n")
            return
        lines.append(f"URL={url}")
        if not name.endswith(".url"):
            name = name + ".url"
        Path(cpane.CPane().currentPath, name).write_text(
            "\n".join(lines), encoding="utf-8"
        )

    job = ckit.JobItem(_access, _make_shortcut)
    window.taskEnqueue(job, create_new_queue=False)


def make_shortcut() -> None:
    pane = cpane.CPane()
    target = pane.selectedItemNames
    if len(target) < 1:
        target.append(pane.focusedItem.getName())

    other_pane_dir = cpane.CPane(False).currentPath
    for name in target:
        lnk_path = str(Path(other_pane_dir, name).with_suffix(".lnk"))
        src_path = str(Path(pane.currentPath, name))
        run_ps1("mklnk", src_path, lnk_path)
        kiritori.log(f"Created shortcut '{lnk_path}'")
