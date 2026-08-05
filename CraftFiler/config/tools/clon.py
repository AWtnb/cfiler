import os
import tempfile
from pathlib import Path

import ckit  # type: ignore

from . import kiritori
from .common import is_file_locked

TEMP_FILE_PREFIX = "cfiler_preview_openxml_"


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    kiritori.setup(window)


def invoke_tempfile_cleaner() -> ckit.ckit_threadutil.CronItem:
    temp_dir = tempfile.gettempdir()

    def _crean(_) -> None:
        count = 0
        for file in os.listdir(temp_dir):
            if file.startswith(TEMP_FILE_PREFIX) and file.endswith(".txt"):
                try:
                    p = Path(temp_dir, file)
                    if not is_file_locked(p):
                        p.unlink()
                        count += 1
                except Exception as e:  # noqa: BLE001
                    kiritori.log(f"Failed to remove temp file :{file}\n{e}")

        if 0 < count:
            msg = f"Removed {count} tempfile"
            if 1 < count:
                msg += "s"
            msg += " for preview."
            window.setStatusMessage(msg, 8000)

    ci = ckit.CronItem(_crean, 30.0)

    return ci


def remove_tempfiles() -> None:
    temp_dir = tempfile.gettempdir()
    paths = []
    for file in os.listdir(temp_dir):
        if file.startswith(TEMP_FILE_PREFIX) and file.endswith(".txt"):
            try:
                os.remove(os.path.join(temp_dir, file))
                paths.append(file)
            except Exception as e:  # noqa: BLE001
                kiritori.log(f"Failed to remove temp file : {e}")

    if len(paths) < 1:
        return

    krtr = kiritori
    count = len(paths)
    msg = f"Removed {count} temp file"
    if 1 < count:
        msg += "s"
    krtr.draw_header(msg)

    for p in paths:
        print("-", p)
    krtr.draw_footer()
