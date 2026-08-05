from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

import ckit  # type: ignore
from cfiler import *  # type: ignore
from cfiler_filelist import item_Default  # type: ignore

from . import kiritori
from .clon import TEMP_FILE_PREFIX
from .common import smart_check_path
from .cpane import CPane


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    kiritori.setup(window)


def read_openxml(path: str) -> str:
    go_tool = {
        ".docx": "docxr.exe",
        ".xlsx": "xlsxr.exe",
    }.get(Path(path).suffix, None)
    if go_tool is None:
        return ""

    exe_path = shutil.which(go_tool)
    if not exe_path:
        kiritori.log(f"'{go_tool}' not found...")
        return ""
    try:
        cmd = [
            exe_path,
            f"-src={path}",
        ]
        proc = subprocess.run(
            cmd,
            capture_output=True,
            encoding="utf-8",
            creationflags=subprocess.CREATE_NO_WINDOW,
            check=False,
        )
        if proc.returncode != 0:
            if o := proc.stdout:
                kiritori.log(o)
            if e := proc.stderr:
                kiritori.log(e)
            return ""
        return proc.stdout
    except Exception as e:  # noqa: BLE001
        kiritori.log(e)
        return ""


def preview_openxml_content(path: str) -> None:
    _, ext = os.path.splitext(path)
    if ext not in [".docx", ".xlsx"]:
        return

    def _write_to_tempfile(job_item: ckit.JobItem) -> None:
        job_item.temp_path = ""
        content = read_openxml(path)
        if not content:
            return
        try:
            tf = tempfile.NamedTemporaryFile(  # noqa: SIM115
                mode="w",
                encoding="utf-8",
                delete=False,
                suffix=".txt",
                prefix=TEMP_FILE_PREFIX,
            )
            tf.write(content)
            tf.close()
            job_item.temp_path = tf.name
        except Exception as e:  # noqa: BLE001
            kiritori.log(e)

    def _view_tempfile(job_item: ckit.JobItem) -> None:
        if job_item.temp_path:
            d, n = os.path.split(job_item.temp_path)
            item = item_Default(d, n)
            window._viewCommon(d, item)

    job = ckit.JobItem(_write_to_tempfile, _view_tempfile)
    window.taskEnqueue(job, create_new_queue=False)


def docx_to_txt() -> None:

    pane = CPane()
    paths = pane.selectedItemPaths
    if len(paths) < 1:
        paths = [pane.focusedItemPath]

    krtr = kiritori

    def _read(_: ckit.JobItem) -> None:
        krtr.draw_header("Converting docx")

        for i, path in enumerate(paths, start=1):
            if not path.endswith(".docx"):
                continue
            docx_name = Path(path).name
            print(f"[{i:02}/{len(paths):02}]{docx_name}")

            new_path = Path(path).with_suffix(".txt")
            content = read_openxml(path)
            if smart_check_path(new_path):
                print(f"==> Skipped ({new_path.name} already exists)")
            else:
                new_path.write_text(content, encoding="utf-8")
                print("==> Converted")
                pane.unSelectByName(docx_name)

    def _write(_: ckit.JobItem) -> None:
        krtr.draw_footer()

    job = ckit.JobItem(_read, _write)
    window.taskEnqueue(job, create_new_queue=False)
