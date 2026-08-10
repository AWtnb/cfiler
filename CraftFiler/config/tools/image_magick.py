import configparser
import shutil
import subprocess
from pathlib import Path

import ckit  # type: ignore

from . import cpane, kiritori
from .common import stringify

INI_SECTION = "IMAGE_MAGICK_CONFIG"
INI_OPTION_NAME = "ext"


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    cpane.setup(window)
    kiritori.setup(window)

    try:
        window.ini.add_section(INI_SECTION)
    except configparser.DuplicateSectionError:
        pass


def change_image_type() -> None:
    exe_name = "magick.exe"
    imagemagick = shutil.which(exe_name)

    if imagemagick is None:
        kiritori.log(f"{exe_name} not found!")
        return

    pane = cpane.CPane()
    targets = pane.selectedItemPaths
    if len(targets) < 1:
        return

    placeholder = ""
    try:
        placeholder = window.ini.get(INI_SECTION, INI_OPTION_NAME)
    except Exception:  # noqa: BLE001, S110
        pass

    ext = stringify(window.commandLine("NewExtension", text=placeholder))
    if ext == "":
        return

    if not ext.startswith("."):
        ext = "." + ext

    window.ini.set(INI_SECTION, INI_OPTION_NAME, ext)

    num = len(targets)
    msg = f"Converting {num} item"
    if 1 < num:
        msg += "s"
    msg += f" to {ext}:\n"

    def _convert(job_item: ckit.JobItem) -> None:
        job_item.converted_names = []

        kiritori.draw_header(msg)
        for i, path in enumerate(targets, start=1):
            p = Path(path)
            new_path = p.with_name(p.stem + ext)
            cmd = [imagemagick, path, str(new_path)]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=False,
            )
            if proc.returncode != 0:
                print(proc.stderr)
            else:
                print(f"[{i:02}/{num:02}]{new_path.name}")
                job_item.converted_names.append(p.name)

    def _finish(job_item: ckit.JobItem) -> None:
        names = job_item.converted_names
        for name in names:
            pane.unSelectByName(name)
        if 0 < len(names):
            kiritori.draw_footer()

    job = ckit.JobItem(_convert, _finish)
    window.taskEnqueue(job, create_new_queue=False)
