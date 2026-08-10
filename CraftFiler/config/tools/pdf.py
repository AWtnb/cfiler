import shutil
import subprocess
from pathlib import Path

import ckit  # type: ignore

from . import cpane, kiritori
from .common import stringify


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window
    cpane.setup(window)
    kiritori.setup(window)


def concatenate_pdf() -> None:
    exe_name = "go-pdfconc.exe"
    exe_path = shutil.which(exe_name)
    if not exe_path:
        kiritori.log(f"'{exe_name}' not found!")
        return

    pane = cpane.CPane()
    if not pane.hasSelection:
        return
    for path in pane.selectedItemPaths:
        p = Path(path)
        if p.is_dir():
            kiritori.log("dir item is selected!")
            return
        if p.suffix != ".pdf":
            kiritori.log("non-pdf file found!")
            return

    basename = stringify(window.commandLine(title="Outname", text="conc"))
    if len(basename) < 1:
        return

    src = "\n".join(pane.selectedItemPaths)

    def _conc(_) -> None:
        window.setProgressValue(None)
        try:
            cmd = [exe_path, "--outname", basename]
            proc = subprocess.run(
                cmd,
                input=src,
                capture_output=True,
                encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
            if proc.returncode != 0:
                kiritori.log(f"ERROR: {proc.stdout}")
        except Exception as e:  # noqa: BLE001
            kiritori.log(e)

    def _finish(job_item: ckit.JobItem) -> None:
        window.clearProgress()
        if job_item.isCanceled():
            kiritori.log("Canceled.")
        else:
            pane.refresh()
            name = basename + ".pdf"
            pane.focusByName(name)
            kiritori.log(f"Concatenated as '{name}':\n\n{src}")

    job = ckit.JobItem(_conc, _finish)
    window.taskEnqueue(job, create_new_queue=False)
