import time
from enum import IntEnum

import ckit  # type: ignore
from cfiler_mainwindow import MainWindow  # type: ignore
from cfiler_misc import getFileSizeString  # type: ignore

from .tools.protocols import ItemDefaultProtocol


class ItemTimestamp:
    def __init__(self, item) -> None:
        self._time = item.time()
        self._now = time.localtime()

    @property
    def date(self) -> str:
        t = self._time
        if t[0] == self._now[0]:
            if t[1] == self._now[1] and t[2] == self._now[2]:
                return ""
            return f"{t[1]:02}-{t[2]:02}"
        return f"{t[0]}-{t[1]:02}-{t[2]:02}"

    @property
    def time(self) -> str:
        t = self._time
        return f"{t[3]:02}:{t[4]:02}:{t[5]:02}"


class ColWidth(IntEnum):
    ext = 6
    size = 6
    date = 11
    time = 9
    area_min = 40


def itemformat_NativeName_Ext_Size_YYYYMMDDorHHMMSS(
    window: MainWindow, item: ItemDefaultProtocol, pane_width: int, _
) -> str:
    timestamp = ItemTimestamp(item)
    date_elem = timestamp.date.rjust(ColWidth.date)
    time_elem = timestamp.time.rjust(ColWidth.time)
    size_elem = (
        "\ud83d\udcc1"
        if item.isdir()
        else getFileSizeString(item.size()).rjust(ColWidth.size)
    )

    meta_elem = size_elem + date_elem + time_elem
    area_width = max(ColWidth.area_min, pane_width)
    filename_width = area_width - len(meta_elem)

    stem, ext = (
        [item.getName(), None]
        if item.isdir()
        else ckit.splitExt(item.getName(), ColWidth.ext)
    )

    if ext:
        stem_width = filename_width - ColWidth.ext
        return (
            ckit.adjustStringWidth(
                window, stem, stem_width, ckit.ALIGN_LEFT, ckit.ELLIPSIS_RIGHT
            )
            + ckit.adjustStringWidth(
                window, ext, ColWidth.ext, ckit.ALIGN_LEFT, ckit.ELLIPSIS_NONE
            )
            + meta_elem
        )
    return (
        ckit.adjustStringWidth(
            window, stem, filename_width, ckit.ALIGN_LEFT, ckit.ELLIPSIS_RIGHT
        )
        + meta_elem
    )


CUSTOM_THEME = {
    "bg": "#122530",
    "fg": "#ffffff",
    "cursor0": "#ffffff",
    "cursor1": "#ff4040",
    "bar_fg": "#000000",
    "bar_error_fg": "#c80000",
    "file_fg": "#e6e6e6",
    "dir_fg": "#f4d71a",
    "hidden_file_fg": "#555555",
    "hidden_dir_fg": "#555532",
    "error_file_fg": "#ff0000",
    "select_file_bg1": "#1451ba",
    "select_file_bg2": "#1451ba",
    "bookmark_file_bg1": "#013a70",
    "bookmark_file_bg2": "#c1077d",
    "file_cursor": "#7fffcb",
    "select_bg": "#1451ba",
    "select_fg": "#ffffff",
    "choice_bg": "#323232",
    "choice_fg": "#ffffff",
    "diff_bg1": "#643232",
    "diff_bg2": "#326432",
    "diff_bg3": "#323264",
}


def setup(window) -> None:
    window.itemformat = itemformat_NativeName_Ext_Size_YYYYMMDDorHHMMSS

    name = "black"
    ckit.ckit_theme.theme_name = name
    window.ini.set("THEME", "name", name)

    for k, v in CUSTOM_THEME.items():
        rgb = tuple(int(v[i : i + 2], 16) for i in (1, 3, 5))
        ckit.ckit_theme.ini.set("COLOR", k, str(rgb))

    window.destroyThemePlane()
    window.createThemePlane()
    window.updateColor()
    window.updateWallpaper()
