import os
import time
from pathlib import Path

import ckit  # ty: ignore[unresolved-import]
import pyauto  # type: ignore

# https://github.com/crftwr/cfiler/blob/master/cfiler_filelist.py
from cfiler_filelist import lister_Default  # type: ignore
from cfiler_listwindow import ListWindow  # type: ignore


def delay(msec: int = 50) -> None:
    time.sleep(msec / 1000)


def setup(window: ckit.TextWindow) -> None:
    window.keymap["E"] = lambda _: None
    window.keymap["Q"] = window.command_Close
    window.keymap["J"] = window.command_ScrollDown
    window.keymap["K"] = window.command_ScrollUp
    window.keymap["C-J"] = window.command_PageDown
    window.keymap["C-K"] = window.command_PageUp
    window.keymap["L"] = window.command_PageDown
    window.keymap["H"] = window.command_PageUp
    window.keymap["Right"] = window.command_PageDown
    window.keymap["Left"] = window.command_PageUp
    window.keymap["F3"] = window.command_SearchNext
    window.keymap["S-F3"] = window.command_SearchPrev

    def to_top(_) -> None:
        window.scroll_info.pos = 0
        window.paint()

    window.keymap["A"] = to_top
    window.keymap["Home"] = to_top

    def to_bottom(_) -> None:
        window.scroll_info.pos = window._numLines() - (window.height() // 2)
        window.paint()

    window.keymap["E"] = to_bottom
    window.keymap["End"] = to_bottom

    def open_with_smooth_csv(_) -> None:
        smooth_csv_path = r"C:\Program Files\SmoothCSV\smoothcsv-app.exe"
        if not os.path.exists(smooth_csv_path):
            return

        pane = window.main_window.activePane()
        path = Path(window.item.getFullpath())

        focused_item_path = Path(pane.file_list.getItem(pane.cursor).getFullpath())
        if focused_item_path.suffix not in [".docx", ".xlsx"]:
            visible = isinstance(pane.file_list.getLister(), lister_Default)
            pane.history.append(str(path.parent), path.name, visible, True)

        window.command_Close(None)
        pyauto.shellExecute(None, smooth_csv_path, str(path), "")

    window.keymap["Comma"] = open_with_smooth_csv

    def open_original(_) -> None:
        pane = window.main_window.activePane()
        focused_item_path = Path(pane.file_list.getItem(pane.cursor).getFullpath())
        path = (
            focused_item_path
            if focused_item_path.suffix in [".docx", ".xlsx"]
            else Path(window.item.getFullpath())
        )
        visible = isinstance(pane.file_list.getLister(), lister_Default)
        pane.history.append(str(path.parent), path.name, visible, True)
        window.command_Close(None)
        pyauto.shellExecute(None, str(path), "", "")

    window.keymap["C-Enter"] = open_original
    window.keymap["C-L"] = open_original

    def get_content() -> str:
        return os.linesep.join(window.lines)

    def copy_content(_) -> None:
        if window.binary:
            return
        c = get_content()
        if len(c) < 1:
            return
        ckit.setClipboardText(c)
        delay(120)
        window.command_Close(None)

    window.keymap["C-C"] = copy_content
    window.keymap["C-Insert"] = copy_content

    def copy_line_at_top(_) -> None:
        if window.binary:
            return
        c = get_content()
        if len(c) < 1:
            return
        idx = window.scroll_info.pos
        line = c.splitlines()[idx]
        ckit.setClipboardText(line)
        delay(120)
        window.command_Close(None)

    window.keymap["C-T"] = copy_line_at_top

    def reload_with_encoding(_) -> None:
        encodes = {
            "(Auto)": "",
            "S-JIS": "cp932",
            "EUC-JP": "euc-jp",
            "JIS": "iso-2022-jp",
            "UTF-8": "utf-8",
            "UTF-16LE": "utf-16-le",
            "UTF-16BE": "utf-16-be",
            "binary": None,
        }
        names = list(encodes.keys())
        pos = window.main_window.centerOfWindowInPixel()

        list_window = ListWindow(
            x=pos[0],
            y=pos[1],
            min_width=40,
            min_height=1,
            max_width=window.width() - 5,
            max_height=window.height() - 3,
            parent_window=window,
            ini=window.ini,
            title="encoding",
            items=names,
            initial_select=0,
            onekey_search=False,
            onekey_decide=False,
            return_modkey=False,
            keydown_hook=None,
            statusbar_handler=None,
        )
        window.enable(False)
        list_window.messageLoop()
        result = list_window.getResult()
        window.enable(True)
        window.activate()
        list_window.destroy()

        if result < 0:
            return

        enc = encodes[names[result]]
        auto_flag = enc is not None and len(enc) < 1
        window.load(auto=auto_flag, encoding=ckit.TextEncoding(enc))

        window.scroll_info.makeVisible(0, window.height() - 1)

    window.keymap["C-Comma"] = reload_with_encoding
    window.keymap["Z"] = reload_with_encoding
