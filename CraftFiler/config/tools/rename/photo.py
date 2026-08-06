from __future__ import annotations

import datetime
import os
from pathlib import Path

from cfiler_resultwindow import popResultWindow  # type: ignore
from PIL import Image as PILImage  # type: ignore
from PIL.ExifTags import TAGS  # type: ignore

from .. import cpane, kiritori
from ..common import TZ_JST
from . import renamer
from .renamer import RenameInfo


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    cpane.setup(window)
    kiritori.setup(window)
    renamer.setup(window)


FILLER_NAME = datetime.datetime.fromtimestamp(0, tz=TZ_JST)


class PhotoFile:
    def __init__(self, path: str):
        self.path = path
        _, self.name = os.path.split(self.path)
        _, self.ext = os.path.splitext(self.name)

    def get_byte_offset(self) -> int:
        ext = self.ext.lower()[1:]
        if ext in ["jpeg", "jpg", "webp"]:
            return 0
        if ext == "raf":
            if self.name.startswith("_DSF"):
                return 0x19E
            return 0x17A
        if ext == "cr2":
            return 0x144
        if self.name.startswith("MVI_") and ext == "mp4":
            return 0x160
        return -1

    def from_exif(self) -> datetime.datetime:
        try:
            with PILImage.open(self.path) as img:
                exif_data = img._getexif()
                if not exif_data:
                    return FILLER_NAME
                for tag_id, value in exif_data.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if tag == "DateTimeOriginal":
                        dt = datetime.datetime.strptime(
                            value, "%Y:%m:%d %H:%M:%S"
                        ).replace(tzinfo=TZ_JST)
                        return dt
                return FILLER_NAME
        except Exception as e:  # noqa: BLE001
            print(e)
            return FILLER_NAME

    def get_timestamp(self) -> datetime.datetime:
        offset = self.get_byte_offset()
        if offset < 1:
            if offset == 0:
                return self.from_exif()
            return FILLER_NAME
        with open(self.path, "rb") as f:
            f.seek(offset)
            bytes_read = f.read(19)
        decoded = bytes_read.decode("ascii")
        return datetime.datetime.strptime(decoded, "%Y:%m:%d %H:%M:%S").replace(
            tzinfo=TZ_JST
        )

    def rename(self, fmt: str) -> str:
        ts = self.get_timestamp().strftime(fmt)
        return ts + "_" + self.name


def execute_with_exif() -> None:
    pane = cpane.CPane()
    targets = []
    for item in renamer.get_renamable_items(pane):
        if not item.isdir():
            targets.append(item)

    if len(targets) < 1:
        return

    def _confirm() -> tuple[list[RenameInfo], bool]:
        infos = []
        lines = []
        for item in targets:
            path = item.getFullpath()
            new_name = PhotoFile(path).rename("%Y_%m%d_%H%M%S00")
            infos.append(RenameInfo(Path(path), new_name))
            lines.append(f"Rename: {item.getName()}\n    ==> {new_name}\n")

        lines.append("\ninsert timestamp:\nOK? (Enter / Esc)")

        return infos, popResultWindow(window, "Preview", "\n".join(lines))

    infos, ok = _confirm()
    if len(infos) < 1 or not ok:
        print("Canceled.\n")
        return

    kiritori.draw_header("Renaming:")
    [renamer.execute(pane, info.orgPath, info.newName) for info in infos]
    kiritori.draw_footer()


def execute_for_lightroom_photo_from_dropbox() -> None:
    pane = cpane.CPane()
    targets = []
    for item in renamer.get_renamable_items(pane):
        if not item.isdir():
            targets.append(item)

    if len(targets) < 1:
        return

    def _confirm() -> tuple[list[RenameInfo], bool]:
        infos = []
        lines = []
        for item in targets:
            path = item.getFullpath()
            p = Path(path)
            elems = p.stem.replace("写真 ", "").split(" ")
            date_ts = elems[0].replace("-", "")
            time_ts = "".join([str(n).rjust(2, "0") for n in elems[1:4]])
            if 4 < len(elems):
                time_ts = time_ts + "-" + elems[-1].replace("(", "").replace(")", "")
            new_name = date_ts + "-IMG_" + time_ts + p.suffix
            infos.append(RenameInfo(p, new_name))
            lines.append(f"Rename: {item.getName()}\n    ==> {new_name}\n")

        lines.append("\ninsert timestamp:\nOK? (Enter / Esc)")

        return infos, popResultWindow(window, "Preview", "\n".join(lines))

    infos, ok = _confirm()
    if len(infos) < 1 or not ok:
        print("Canceled.\n")
        return

    krtr = kiritori
    krtr.draw_header("Renaming:")
    [renamer.execute(pane, info.orgPath, info.newName) for info in infos]
    krtr.draw_footer()
