import datetime
import hashlib
import inspect
import os
import re
import shutil
import subprocess
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

from PIL import ImageGrab

from pathlib import Path
from typing import List, Tuple, Callable, Union, NamedTuple

import ckit
import pyauto

from cfiler import *


# https://github.com/crftwr/cfiler/blob/master/cfiler_mainwindow.py
from cfiler_mainwindow import (
    MainWindow,
    History,
    PAINT_LEFT_LOCATION,
    PAINT_LEFT_HEADER,
    PAINT_LEFT_ITEMS,
    PAINT_LEFT_FOOTER,
    PAINT_RIGHT_LOCATION,
    PAINT_RIGHT_HEADER,
    PAINT_RIGHT_ITEMS,
    PAINT_RIGHT_FOOTER,
    PAINT_FOCUSED_LOCATION,
    PAINT_FOCUSED_HEADER,
    PAINT_FOCUSED_ITEMS,
    PAINT_FOCUSED_FOOTER,
    PAINT_VERTICAL_SEPARATOR,
    PAINT_LOG,
    PAINT_STATUS_BAR,
    PAINT_LEFT,
    PAINT_RIGHT,
    PAINT_FOCUSED,
    PAINT_UPPER,
    PAINT_ALL,
)

# https://github.com/crftwr/cfiler/blob/master/cfiler_filelist.py
from cfiler_filelist import (
    FileList,
    item_Base,
    lister_Default,
    item_Empty,
    filter_Default,
)

# https://github.com/crftwr/cfiler/blob/master/cfiler_listwindow.py
from cfiler_listwindow import ListWindow, ListItem

# https://github.com/crftwr/cfiler/blob/master/cfiler_textviewer.py
from cfiler_textviewer import TextViewer

# https://github.com/crftwr/cfiler/blob/master/cfiler_renamewindow.py
from cfiler_resultwindow import popResultWindow

# https://github.com/crftwr/cfiler/blob/master/cfiler_misc.py
from cfiler_misc import getFileSizeString

import cfiler_resource


class PaintOption:
    LeftLocation = PAINT_LEFT_LOCATION
    LeftHeader = PAINT_LEFT_HEADER
    LeftItems = PAINT_LEFT_ITEMS
    LeftFooter = PAINT_LEFT_FOOTER
    RightLocation = PAINT_RIGHT_LOCATION
    RightHeader = PAINT_RIGHT_HEADER
    RightItems = PAINT_RIGHT_ITEMS
    RightFooter = PAINT_RIGHT_FOOTER
    FocusedLocation = PAINT_FOCUSED_LOCATION
    FocusedHeader = PAINT_FOCUSED_HEADER
    FocusedItems = PAINT_FOCUSED_ITEMS
    FocusedFooter = PAINT_FOCUSED_FOOTER
    VerticalSeparator = PAINT_VERTICAL_SEPARATOR
    Log = PAINT_LOG
    StatusBar = PAINT_STATUS_BAR
    Left = PAINT_LEFT
    Right = PAINT_RIGHT
    Focused = PAINT_FOCUSED
    Upper = PAINT_UPPER
    All = PAINT_ALL


PO = PaintOption()
USER_PROFILE = os.environ.get("USERPROFILE", "")


def delay(msec: int = 50) -> None:
    time.sleep(msec / 1000)


def smart_check_path(
    path: Union[str, Path], timeout_sec: Union[int, float, None] = None
) -> bool:
    """CASE-INSENSITIVE path check with timeout"""
    p = path if type(path) is Path else Path(path)
    try:
        future = ThreadPoolExecutor(max_workers=1).submit(p.exists)
        return future.result(timeout_sec)
    except:
        return False


class LocalApps:

    def __init__(self, app_dict: dict) -> None:
        self.dict = app_dict

    @property
    def names(self) -> list:
        names = []
        for name, path in self.dict.items():
            if smart_check_path(path):
                names.append(name)
        return names

    def get_path(self, name: str) -> str:
        return self.dict.get(name, "")


PDF_VIEWERS = LocalApps(
    {
        "sumatra": r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
        "adobe": r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe",
        "xchange editor": r"C:\Program Files\Tracker Software\PDF Editor\PDFXEdit.exe",
    }
)

TEXT_EDITORS = LocalApps(
    {
        "notepad": r"C:\Windows\System32\notepad.exe",
        "mery": os.path.join(USER_PROFILE, r"AppData\Local\Programs\Mery\Mery.exe"),
        "vscode": os.path.join(USER_PROFILE, r"scoop\apps\vscode\current\Code.exe"),
    }
)


def invoke_listwindow(
    window: ckit.TextWindow, prompt: str, items, ini_pos: int = 0
) -> Tuple[int, int]:
    pos = (
        window.main_window.centerOfWindowInPixel()
        if type(window) is TextViewer
        else window.centerOfFocusedPaneInPixel()
    )
    list_window = ListWindow(
        x=pos[0],
        y=pos[1],
        min_width=40,
        min_height=1,
        max_width=window.width() - 5,
        max_height=window.height() - 3,
        parent_window=window,
        ini=window.ini,
        title=prompt,
        items=items,
        initial_select=ini_pos,
        onekey_search=False,
        onekey_decide=False,
        return_modkey=True,
        keydown_hook=None,
        statusbar_handler=None,
    )
    window.enable(False)
    list_window.messageLoop()
    result, mod = list_window.getResult()
    window.enable(True)
    window.activate()
    list_window.destroy()
    return result, mod


def configure(window: MainWindow) -> None:
    class ItemTimestamp:
        def __init__(self, item) -> None:
            self._time = item.time()
            self._now = time.localtime()

        def _datestr(self) -> str:
            t = self._time
            if t[0] == self._now[0]:
                if t[1] == self._now[1] and t[2] == self._now[2]:
                    return " " * 10
                return " " * 5 + "{:02}-{:02}".format(t[1], t[2])
            return "{}-{:02}-{:02}".format(t[0], t[1], t[2])

        def _timestr(self) -> str:
            t = self._time
            return "{:02}:{:02}:{:02}".format(t[3], t[4], t[5])

        def tostr(self) -> str:
            return self._datestr() + " " + self._timestr()

    def itemformat_NativeName_Ext_Size_YYYYMMDDorHHMMSS(window, item, width, _):
        if item.isdir():
            str_size = "<DIR>"
        else:
            str_size = getFileSizeString(item.size()).rjust(6)

        str_size_time = str_size + " " + ItemTimestamp(item).tostr()

        width = max(40, width)
        filename_width = width - len(str_size_time)

        if item.isdir():
            body, ext = item.getName(), None
        else:
            body, ext = ckit.splitExt(item.getName())

        if ext:
            body_width = min(width, filename_width - 6)
            return (
                ckit.adjustStringWidth(
                    window, body, body_width, ckit.ALIGN_LEFT, ckit.ELLIPSIS_RIGHT
                )
                + ckit.adjustStringWidth(
                    window, ext, 6, ckit.ALIGN_LEFT, ckit.ELLIPSIS_NONE
                )
                + str_size_time
            )
        return (
            ckit.adjustStringWidth(
                window, body, filename_width, ckit.ALIGN_LEFT, ckit.ELLIPSIS_RIGHT
            )
            + str_size_time
        )

    window.itemformat = itemformat_NativeName_Ext_Size_YYYYMMDDorHHMMSS

    class Themer:
        def __init__(self, color: str) -> None:

            if color == "black":
                colortable = {
                    "bg": (0, 0, 0),
                    "fg": (255, 255, 255),
                    "cursor0": (255, 255, 255),
                    "cursor1": (255, 64, 64),
                    "bar_fg": (0, 0, 0),
                    "bar_error_fg": (200, 0, 0),
                    "file_fg": (255, 255, 255),
                    "dir_fg": (255, 255, 150),
                    "hidden_file_fg": (85, 85, 85),
                    "hidden_dir_fg": (85, 85, 50),
                    "error_file_fg": (255, 0, 0),
                    "select_file_bg1": (30, 100, 150),
                    "select_file_bg2": (60, 200, 255),
                    "bookmark_file_bg2": (100, 70, 0),
                    "bookmark_file_bg1": (140, 110, 0),
                    "file_cursor": (255, 128, 128),
                    "select_bg": (30, 100, 150),
                    "select_fg": (255, 255, 255),
                    "choice_bg": (50, 50, 50),
                    "choice_fg": (255, 255, 255),
                    "diff_bg1": (100, 50, 50),
                    "diff_bg2": (50, 100, 50),
                    "diff_bg3": (50, 50, 100),
                }
            else:
                colortable = {
                    "bg": (255, 255, 255),
                    "fg": (0, 0, 0),
                    "cursor0": (255, 255, 255),
                    "cursor1": (0, 255, 255),
                    "bar_fg": (255, 255, 255),
                    "bar_error_fg": (255, 0, 0),
                    "file_fg": (0, 0, 0),
                    "dir_fg": (100, 50, 0),
                    "hidden_file_fg": (100, 100, 100),
                    "hidden_dir_fg": (200, 150, 100),
                    "error_file_fg": (255, 0, 0),
                    "select_file_bg1": (60, 150, 220),
                    "select_file_bg2": (80, 200, 255),
                    "bookmark_file_bg2": (220, 150, 50),
                    "bookmark_file_bg1": (255, 200, 50),
                    "file_cursor": (255, 70, 70),
                    "select_bg": (70, 200, 255),
                    "select_fg": (0, 0, 0),
                    "choice_bg": (150, 150, 150),
                    "choice_fg": (0, 0, 0),
                    "diff_bg1": (100, 50, 50),
                    "diff_bg2": (50, 100, 50),
                    "diff_bg3": (50, 50, 100),
                }
            self._theme_path = Path(ckit.getAppExePath(), "theme", color, "theme.ini")
            self._data = colortable

        def update(self, key: str, value: str) -> None:
            if key not in self._data:
                return
            if type(value) is tuple:
                self._data[key] = value
                return
            colorcode = value.strip("#")
            if len(colorcode) == 6:
                r, g, b = colorcode[:2], colorcode[2:4], colorcode[4:6]
                try:
                    rgb = tuple(int(c, 16) for c in [r, g, b])
                    self._data[key] = rgb
                except Exception as e:
                    Kiritori.log(e)

        def to_string(self) -> str:
            lines = ["[COLOR]"]
            for key, value in self._data.items():
                line = "{} = {}".format(key, value)
                lines.append(line)
            return "\n".join(lines)

        def overwrite(self) -> None:
            theme = self.to_string()
            if (
                not smart_check_path(self._theme_path)
                or self._theme_path.read_text() != theme
            ):
                self._theme_path.write_text(theme)

    def set_theme(theme_table: dict):
        color = window.ini.get("THEME", "name")
        t = Themer(color)
        for k, v in theme_table.items():
            t.update(k, v)
        t.overwrite()

    CUSTOM_THEME = {
        "bg": "#122530",
        "fg": "#FFFFFF",
        "cursor0": "#FFFFFF",
        "cursor1": "#FF4040",
        "bar_fg": "#000000",
        "bar_error_fg": "#C80000",
        "file_fg": "#E6E6E6",
        "dir_fg": "#F4D71A",
        "hidden_file_fg": "#555555",
        "hidden_dir_fg": "#555532",
        "error_file_fg": "#FF0000",
        "select_file_bg1": "#1E6496",
        "select_file_bg2": "#1E6496",
        "bookmark_file_bg1": "#6B3A70",
        "bookmark_file_bg2": "#6B3A70",
        "file_cursor": "#7FFFBB",
        "select_bg": "#1E6496",
        "select_fg": "#FFFFFF",
        "choice_bg": "#323232",
        "choice_fg": "#FFFFFF",
        "diff_bg1": "#643232",
        "diff_bg2": "#326432",
        "diff_bg3": "#323264",
    }
    set_theme(CUSTOM_THEME)

    class Kiritori:
        sep = "-"

        @staticmethod
        def get_width() -> int:
            return window.width()

        @classmethod
        def _draw_header(cls) -> None:
            ts = datetime.datetime.today().strftime(
                " %Y-%m-%d %H:%M:%S.%f {}".format(cls.sep * 2)
            )
            print("\n{}".format(ts.rjust(cls.get_width(), cls.sep)))

        @classmethod
        def _draw_footer(cls) -> None:
            print("{}\n".format(cls.sep * cls.get_width()))

        @classmethod
        def log(cls, s) -> None:
            cls._draw_header()
            print(s)
            cls._draw_footer()

        @classmethod
        def wrap(cls, func: Callable) -> None:
            cls._draw_header()
            func()
            cls._draw_footer()

    def reset_default_keys(keys: list) -> None:
        for key in keys:
            window.keymap[key] = lambda _: None

    reset_default_keys(
        [
            "Q",
            "Colon",
            "S-Colon",
            "Period",
            "S-Period",
            "BackSlash",
        ]
    )

    def apply_cfiler_command(mapping: dict) -> None:
        for key, func in mapping.items():
            window.keymap[key] = func

    apply_cfiler_command(
        {
            "C": window.command_Copy,
            "M": window.command_Move,
            "S-Enter": window.command_View,
            "C-S-Q": window.command_CancelTask,
            "C-Q": window.command_Quit,
            "A-F4": window.command_Quit,
            "C-Comma": window.command_ConfigMenu,
            "C-S-Comma": window.command_ConfigMenu2,
            "C-H": window.command_JumpHistory,
            "C-Z": window.command_JumpHistory,
            "Back": window.command_JumpHistory,
            "C-D": window.command_Delete,
            "C-A-D": window.command_SelectDrive,
            "P": window.command_FocusOther,
            "C-Right": window.command_FocusOther,
            "O": window.command_ChdirActivePaneToOther,
            "S-O": window.command_ChdirInactivePaneToOther,
            "A": window.command_CursorTop,
            "E": window.command_CursorBottom,
            "Home": window.command_CursorTop,
            "End": window.command_CursorBottom,
            "C-S-P": window.command_CommandLine,
            "H": window.command_GotoParentDir,
            "Left": window.command_GotoParentDir,
            "S-F10": window.command_ContextMenu,
            "A-S-F10": window.command_ContextMenuDir,
            "Apps": window.command_ContextMenu,
            "S-Apps": window.command_ContextMenuDir,
            "C-A-N": window.command_DuplicateCfiler,
            "OpenBracket": window.command_MoveSeparatorLeft,
            "CloseBracket": window.command_MoveSeparatorRight,
            "Yen": window.command_MoveSeparatorCenter,
            "A-S": window.command_SetSorter,
            "A-C-J": window.command_LogDown,
            "A-C-K": window.command_LogUp,
            "A-C-Down": window.command_LogDown,
            "A-C-Up": window.command_LogUp,
            "S-OpenBracket": window.command_MoveSeparatorUp,
            "S-CloseBracket": window.command_MoveSeparatorDown,
        }
    )

    class Keybinder:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

        @staticmethod
        def wrap(func: Callable) -> Callable:
            if inspect.signature(func).parameters.items():

                def _callback_with_arg(arg) -> None:
                    func(arg)

                return _callback_with_arg

            def _callback(_) -> None:
                func()

            return _callback

        def bind(self, key: str, func: Callable) -> None:
            self._window.keymap[key] = self.wrap(func)

    KEYBINDER = Keybinder(window)

    def check_log_selected() -> bool:
        selection_left, selection_right = window.log_pane.selection
        return selection_left != selection_right

    class CPane:
        def __init__(self, window: MainWindow, active: bool = True) -> None:
            self._window = window
            if active:
                self._pane = self._window.activePane()
                self._items = self._window.activeItems()
            else:
                self._pane = self._window.inactivePane()
                self._items = self._window.inactiveItems()

        @property
        def entity(self):
            return self._pane

        def repaint(self, option: PaintOption = PO.All) -> None:
            self._window.paint(option)

        def refresh(self) -> None:
            self._window.subThreadCall(self.fileList.refresh, (False, True))
            self.fileList.applyItems()

        @property
        def items(self) -> list:
            if self.isBlank:
                return []
            return self._items

        @property
        def dirs(self) -> list:
            items = []
            if self.isBlank:
                return items
            for i in range(self.count):
                item = self.byIndex(i)
                if item.isdir():
                    items.append(item)
            return items

        @property
        def files(self) -> list:
            items = []
            if self.isBlank:
                return items
            for i in range(self.count):
                item = self.byIndex(i)
                if not item.isdir():
                    items.append(item)
            return items

        @property
        def stems(self) -> list:
            items = []
            if self.isBlank:
                return items
            for i in range(self.count):
                path = self.pathByIndex(i)
                items.append(Path(path).stem)
            return items

        def appendHistory(self, path: str, mark: bool = False) -> None:
            p = Path(path)
            lister = self.lister
            visible = isinstance(lister, lister_Default)
            self.entity.history.append(str(p.parent), p.name, visible, mark)

        @property
        def cursor(self) -> int:
            return self._pane.cursor

        def focus(self, i: int) -> None:
            if self.isValidIndex(i):
                self._pane.cursor = i
                self.scrollToCursor()

        def byName(self, name: str) -> int:
            return self.fileList.indexOf(name)

        def hasName(self, name: str) -> bool:
            return self.byName(name) != -1

        def focusByName(self, name: str) -> None:
            sep = "/"
            if os.sep in name or sep in name:
                name = name.replace(os.sep, sep).split(sep)[0]
            i = self.byName(name)
            if self.isValidIndex(i):
                self.focus(i)

        def focusOther(self) -> None:
            self._window.command_FocusOther(None)

        @property
        def fileList(self) -> FileList:
            return self._pane.file_list

        @property
        def lister(self):
            return self.fileList.getLister()

        @property
        def hasSelection(self) -> bool:
            return self.fileList.selected()

        @property
        def hasBookmark(self) -> bool:
            for item in self.items:
                if item.bookmark():
                    return True
            return False

        @property
        def scrollInfo(self) -> ckit.ScrollInfo:
            return self._pane.scroll_info

        @property
        def currentPath(self) -> str:
            return self.fileList.getLocation()

        @property
        def count(self) -> int:
            return self.fileList.numItems()

        def byIndex(self, i: int) -> item_Base:
            return self.fileList.getItem(i)

        @property
        def isBlank(self) -> bool:
            return isinstance(self.byIndex(0), item_Empty)

        @property
        def names(self) -> list:
            names = []
            if self.isBlank:
                return names
            for i in range(self.count):
                item = self.byIndex(i)
                names.append(item.getName())
            return names

        @property
        def paths(self) -> list:
            return [os.path.join(self.currentPath, name) for name in self.names]

        @property
        def extensions(self) -> list:
            exts = []
            if self.isBlank:
                return exts
            for i in range(self.count):
                path = Path(self.pathByIndex(i))
                ext = path.suffix.replace(".", "")
                if path.is_file() and ext not in exts:
                    exts.append(ext)
            return exts

        @property
        def selectedItems(self) -> list:
            items = []
            if self.isBlank:
                return items
            for i in range(self.count):
                item = self.byIndex(i)
                if item.selected():
                    items.append(item)
            return items

        @property
        def selectedOrAllItems(self) -> list:
            if self.hasSelection:
                return self.selectedItems
            return self.items

        @property
        def selectedItemPaths(self) -> list:
            return [item.getFullpath() for item in self.selectedItems]

        @property
        def selectedItemNames(self) -> list:
            return [item.getName() for item in self.selectedItems]

        @property
        def focusedItem(self) -> Union[item_Base, None]:
            if self.isBlank:
                return None
            return self.byIndex(self.cursor)

        def pathByIndex(self, i: int) -> str:
            item = self.byIndex(i)
            return item.getFullpath()

        @property
        def focusedItemPath(self) -> str:
            if self.isBlank:
                return ""
            return self.pathByIndex(self.cursor)

        def applySelectionHighlight(self) -> None:
            self.repaint(PO.Upper)

        def isValidIndex(self, i: int) -> bool:
            if self.isBlank:
                return False
            if i < 0:
                return False
            if self.count - 1 < i:
                return False
            return True

        def toggleSelection(self, i: int) -> None:
            if self.isValidIndex(i):
                self.fileList.selectItem(i, None)
                self.applySelectionHighlight()

        def setSelectionState(self, i: int, state: bool) -> None:
            if self.isValidIndex(i):
                self.fileList.selectItem(i, state)
                self.applySelectionHighlight()

        def select(self, i: int) -> None:
            self.setSelectionState(i, True)

        def selectAll(self) -> None:
            for i in range(self.count):
                self.select(i)

        def unSelect(self, i: int) -> None:
            self.setSelectionState(i, False)

        def unSelectAll(self) -> None:
            for i in range(self.count):
                self.unSelect(i)

        def selectByName(self, name: str) -> None:
            i = self.byName(name)
            if i < 0:
                return
            self.select(i)
            self.applySelectionHighlight()

        def unSelectByName(self, name: str) -> None:
            i = self.byName(name)
            if i < 0:
                return
            self.unSelect(i)
            self.applySelectionHighlight()

        def selectByNames(self, names: list) -> None:
            for name in names:
                self.selectByName(name)

        @property
        def selectionTop(self) -> int:
            if not self.hasSelection:
                return -1
            for i in range(self.count):
                if self.byIndex(i).selected():
                    return i
            return -1

        @property
        def selectionBottom(self) -> int:
            if not self.hasSelection:
                return -1
            idxs = []
            for i in range(self.count):
                if self.byIndex(i).selected():
                    idxs.append(i)
            if len(idxs) < 1:
                return -1
            return idxs[-1]

        def scrollTo(self, i: int) -> None:
            self.scrollInfo.makeVisible(i, self._window.fileListItemPaneHeight(), 1)
            self.repaint(PO.FocusedItems)

        def scrollToCursor(self) -> None:
            self.scrollTo(self.cursor)

        def openChild(self, name: str) -> None:
            self.openPath(os.path.join(self.currentPath, name))

        def openPath(self, path: str, focus_name: Union[None, str] = None) -> None:
            target = Path(path)
            if not smart_check_path(target, 2.0):
                Kiritori.log("invalid path: '{}'".format(path))
                return
            if target.is_file():
                path = str(target.parent)
                focus_name = target.name
            lister = lister_Default(self._window, path)
            self._window.jumpLister(self._pane, lister, focus_name)

        def touch(self, name: str) -> None:
            if not hasattr(self.lister, "touch"):
                Kiritori.log("cannot make file here.")
                return
            dp = Path(self.currentPath, name)
            if smart_check_path(dp) and dp.is_file():
                Kiritori.log("file '{}' already exists.".format(name))
                return
            self._window.subThreadCall(self.lister.touch, (name,))
            self.refresh()
            self.focus(self._window.cursorFromName(self.fileList, name))

        def mkdir(self, name: str, focus: bool = True) -> None:
            if not hasattr(self.lister, "mkdir"):
                Kiritori.log("cannot make directory here.")
                return
            dp = Path(self.currentPath, name)
            if smart_check_path(dp) and dp.is_dir():
                Kiritori.log("directory '{}' already exists.".format(name))
                self.focusByName(name)
                return
            self._window.subThreadCall(self.lister.mkdir, (name, None))
            self.refresh()
            if focus:
                self.focusByName(name)

        def copyToChild(
            self, dest_name: str, items: list, remove_origin: bool = False
        ) -> None:
            mode = "m" if remove_origin else "c"
            child_lister = self.lister.getChild(dest_name)
            window._copyMoveCommon(
                self.entity,
                self.lister,
                child_lister,
                items,
                mode,
                self.fileList.getFilter(),
            )
            child_lister.destroy()

        def traverse(self) -> List[str]:
            paths = []
            for item in self.items:
                if item.isdir():
                    if item.getName().startswith("."):
                        continue
                    for _, _, files in item.walk():
                        for file in files:
                            paths.append(file.getFullpath())
                else:
                    paths.append(item.getFullpath())
            return paths

    class LeftPane(CPane):
        def __init__(self, window: MainWindow) -> None:
            super().__init__(window, (window.focus == MainWindow.FOCUS_LEFT))

        def activate(self) -> None:
            if self._window.focus == MainWindow.FOCUS_RIGHT:
                self._window.focus = MainWindow.FOCUS_LEFT
            self.repaint(PO.Left | PO.Right)

    class RightPane(CPane):
        def __init__(self, window: MainWindow) -> None:
            super().__init__(window, (window.focus == MainWindow.FOCUS_RIGHT))

        def activate(self) -> None:
            if self._window.focus == MainWindow.FOCUS_LEFT:
                self._window.focus = MainWindow.FOCUS_RIGHT
            self.repaint(PO.Left | PO.Right)

    def smart_cursorUp(_) -> None:
        pane = CPane(window)
        if pane.isBlank or pane.count == 1:
            return
        if pane.cursor == 0:
            pane.entity.cursor = pane.count - 1
        else:
            pane.entity.cursor -= 1
        pane.scrollToCursor()

    KEYBINDER.bind("K", smart_cursorUp)
    KEYBINDER.bind("Up", smart_cursorUp)

    def smart_cursorDown(_) -> None:
        pane = CPane(window)
        if pane.isBlank or pane.count == 1:
            return
        if pane.cursor == pane.count - 1:
            pane.entity.cursor = 0
        else:
            pane.entity.cursor += 1
        pane.scrollToCursor()

    KEYBINDER.bind("J", smart_cursorDown)
    KEYBINDER.bind("Down", smart_cursorDown)

    def shell_exec(path: str, *args) -> None:
        if type(path) is not str:
            path = str(path)
        params = []
        for arg in args:
            if len(arg.strip()):
                if " " in arg:
                    params.append('"{}"'.format(arg))
                else:
                    params.append(arg)
        try:
            pyauto.shellExecute(None, path, " ".join(params), "")
        except:
            Kiritori.log("invalid path: '{}'".format(path))

    def toggle_pane_width() -> None:
        half = (window.width() - 1) // 2
        if window.focus == MainWindow.FOCUS_LEFT:
            if window.left_window_width == half:
                window.left_window_width = window.width() - 1
            else:
                window.left_window_width = half
        else:
            if window.left_window_width == half:
                window.left_window_width = 0
            else:
                window.left_window_width = half
        window.updateThemePosSize()
        window.paint(PO.Upper)

    KEYBINDER.bind("C-S", toggle_pane_width)

    def smart_focus_other() -> None:
        window.command_FocusOther(None)
        min_width = 10
        if window.focus == MainWindow.FOCUS_LEFT:
            if min_width < window.left_window_width:
                return
        else:
            if window.left_window_width < window.width() - min_width:
                return
        window.command_MoveSeparatorCenter(None)

    KEYBINDER.bind("C-L", smart_focus_other)

    class ExtensionChecker:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

            self._archivers = []
            for archiver in self._window.archiver_list:
                for ext in archiver[0].split():
                    self._archivers.append(ext[1:])
            self._images = window.image_file_ext_list
            self._musics = window.music_file_ext_list

        def is_archiver(self, ext: str) -> bool:
            return ext in self._archivers

        def is_image(self, ext: str) -> bool:
            return ext in self._images

        def is_music(self, ext: str) -> bool:
            return ext in self._musics

    EXTENSION_CHECKER = ExtensionChecker(window)

    def copy_docx_content(path) -> None:
        if not path.endswith(".docx"):
            return

        def _read(job_item: ckit.JobItem) -> None:
            job_item.result = read_docx(path)

        def _view(job_item: ckit.JobItem) -> None:
            ckit.setClipboardText(job_item.result)
            Kiritori.log("Copied content: '{}'".format(path))

        job = ckit.JobItem(_read, _view)
        window.taskEnqueue(job, create_new_queue=False)

    def hook_enter() -> bool:
        # returning `True` hooks (skips) default action.

        pane = CPane(window)
        if pane.isBlank:
            smart_focus_other()
            return True

        focus_path = pane.focusedItemPath
        p = Path(focus_path)
        if p.is_dir():
            return False

        if pane.focusedItem.size() == 0:
            window.command_Execute(None)
            return True

        ext = p.suffix

        if EXTENSION_CHECKER.is_image(ext):
            pane.appendHistory(focus_path, True)
            return False

        if EXTENSION_CHECKER.is_archiver(ext):
            return True

        if EXTENSION_CHECKER.is_music(ext):
            window.command_Execute(None)
            return True

        if ext[1:].lower() in [
            "m4a",
            "mp4",
            "pdf",
            "xlsx",
            "xls",
            "doc",
            "pptx",
            "ppt",
        ]:
            window.command_Execute(None)
            return True

        if ext == ".docx":
            menu = ["Open", "Copy content"]
            result, _ = invoke_listwindow(window, "docx file:", menu)
            if result == 0:
                window.command_Execute(None)
            elif result == 1:
                copy_docx_content(focus_path)
            return True

        return False

    window.enter_hook = hook_enter

    KEYBINDER.bind("L", window.command_Enter)
    KEYBINDER.bind("Right", window.command_Enter)

    def toggle_hidden() -> None:
        window.showHiddenFile(not window.isHiddenFileVisible())

    KEYBINDER.bind("C-S-H", toggle_hidden)

    def open_with() -> None:
        pane = CPane(window)
        if pane.isBlank or pane.focusedItem.isdir():
            return

        paths = pane.selectedItemPaths
        if len(paths) < 1:
            paths.append(pane.focusedItemPath)

        with_pdf_viewer = True
        for path in paths:
            if Path(path).suffix != ".pdf":
                with_pdf_viewer = False

        apps = PDF_VIEWERS if with_pdf_viewer else TEXT_EDITORS

        if not with_pdf_viewer and 1 < len(paths):
            return

        names = apps.names
        if len(names) < 1:
            return

        result, _ = invoke_listwindow(window, "open with:", names)
        if result < 0:
            return

        exe_path = apps.get_path(names[result])
        for path in paths:
            shell_exec(exe_path, path)

    KEYBINDER.bind("C-O", open_with)

    def quick_move() -> None:
        if not CPane(window).hasSelection:
            window.command_Select(None)
        window.command_Move(None)

    KEYBINDER.bind("M", quick_move)

    def quick_copy() -> None:
        if not CPane(window).hasSelection:
            window.command_Select(None)
        window.command_Copy(None)

    KEYBINDER.bind("C", quick_copy)

    def swap_pane() -> None:
        active = CPane(window, True)
        active_selects = active.selectedItemNames
        active_path = active.currentPath
        active_focus_name = None if active.isBlank else active.focusedItem.getName()

        inactive = CPane(window, False)
        inactive_selects = inactive.selectedItemNames
        inactive_path = inactive.currentPath

        inactive_focus_name = (
            None if inactive.isBlank else inactive.focusedItem.getName()
        )

        active.openPath(inactive_path, inactive_focus_name)
        active.selectByNames(inactive_selects)

        inactive.openPath(active_path, active_focus_name)
        inactive.selectByNames(active_selects)

        LeftPane(window).activate()

    KEYBINDER.bind("S", swap_pane)

    def check_fzf() -> bool:
        paths = os.environ.get("PATH", "").split(os.pathsep)
        for path in paths:
            p = Path(path, "fzf.exe")
            if smart_check_path(p):
                return True
        return False

    class FuzzyBookmark:
        alias_config = os.path.join(USER_PROFILE, r"Personal\alias.txt")

        def __init__(self, window: MainWindow) -> None:
            self._bookmarks = [path for path in window.bookmark.getItems()]

        def load_config(self) -> dict:
            d = {}
            if not smart_check_path(self.alias_config):
                return d
            lines = Path(self.alias_config).read_text("utf-8").splitlines()
            for line in lines:
                if 0 < len(line.strip()) and "=" in line:
                    pair = [s.strip() for s in line.split("=")]
                    d[pair[0]] = pair[1]
            return d

        @staticmethod
        def get_name(path: str) -> str:
            path = path.rstrip(os.sep)
            p = Path(path)
            if 0 < len(p.name):
                return p.name
            return path.split(os.sep)[-1]

        @property
        def name_path_table(self) -> dict:
            alias_mapping = self.load_config()
            d = {}
            for bookmark_path in self._bookmarks:
                name = self.get_name(bookmark_path)
                if 0 < len(alias := alias_mapping.get(bookmark_path, "")):
                    name = "{}::{}".format(alias, name)
                d[name] = bookmark_path
            return d

        def fzf(self) -> str:
            table = self.name_path_table
            src = "\n".join(sorted(table.keys(), reverse=True))
            try:
                cmd = ["fzf.exe"]
                proc = subprocess.run(
                    cmd, input=src, capture_output=True, encoding="utf-8"
                )
                if proc.returncode != 0:
                    if o := proc.stdout:
                        Kiritori.log(o)
                    if e := proc.stderr:
                        Kiritori.log(e)
                    return ""
                return table.get(proc.stdout.strip(), "")
            except Exception as e:
                Kiritori.log(e)
                return ""

    def fuzzy_bookmark() -> None:
        if not check_fzf():
            Kiritori.log("fzf.exe not found.")
            return

        pane = CPane(window)

        def _get_path(job_item: ckit.JobItem) -> None:
            fb = FuzzyBookmark(window)
            job_item.path = fb.fzf()

        def _open(job_item: ckit.JobItem) -> None:
            path = job_item.path
            if 0 < len(path):
                pane.openPath(path)

        job = ckit.JobItem(_get_path, _open)
        window.taskEnqueue(job, create_new_queue=False)

    KEYBINDER.bind("B", fuzzy_bookmark)

    def set_bookmark_alias() -> None:
        pane = CPane(window)
        target = pane.currentPath
        if pane.hasSelection:
            if 1 < len(pane.selectedItems):
                Kiritori.log(
                    "Canceled. Select just 1 item (or nothing to bookmark current location)."
                )
                return
            else:
                target = pane.selectedItemPaths[0]

        result = window.commandLine("Bookmark alias")
        if not result:
            return
        alias = result.strip()
        if len(alias) < 1:
            return

        entries = []
        p = FuzzyBookmark.alias_config
        if smart_check_path(p):
            entries = Path(p).read_text("utf-8").splitlines()
        entries.append("{}={}".format(target, alias))

        Path(p).write_text("\n".join(entries), "utf-8")

        if target not in window.bookmark.getItems():
            window.bookmark.append(target)
            if target != pane.currentPath:
                pane.refresh()
        Kiritori.log("Registered '{}' as alias for '{}'".format(alias, target))

    def read_docx(path: str) -> str:
        exe_path = os.path.join(USER_PROFILE, r"Personal\tools\bin\docxr.exe")
        if not smart_check_path(exe_path):
            Kiritori.log("'{}' not found...".format(exe_path))
            return ""
        try:
            cmd = [
                exe_path,
                "-src={}".format(path),
            ]
            proc = subprocess.run(
                cmd,
                capture_output=True,
                encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if proc.returncode != 0:
                if o := proc.stdout:
                    Kiritori.log(o)
                if e := proc.stderr:
                    Kiritori.log(e)
                return ""
            return proc.stdout
        except Exception as e:
            Kiritori.log(e)
            return ""

    def docx_to_txt() -> None:
        def _convert(path: str) -> None:
            if not path.endswith(".docx"):
                return

            def __read(job_item: ckit.JobItem) -> None:
                job_item.result = read_docx(path)

            def __write(job_item: ckit.JobItem) -> None:
                new_path = Path(path).with_suffix(".txt")
                if smart_check_path(new_path):
                    Kiritori.log("Path duplicates: '{}'".format(new_path))
                else:
                    new_path.write_text(job_item.result, encoding="utf-8")

            job = ckit.JobItem(__read, __write)
            window.taskEnqueue(job, create_new_queue=False)

        pane = CPane(window)
        paths = pane.selectedItemPaths
        if len(paths) < 1:
            paths = [pane.focusedItemPath]

        for path in paths:
            _convert(path)

    class DirRule:
        def __init__(self, current_path: str, src_name: str = ".dirnames") -> None:
            self._current_path = current_path
            self._src_name = src_name

        def read_src(self) -> str:
            p = Path(self._current_path)
            for path in p.parents:
                f = Path(path, self._src_name)
                if smart_check_path(f):
                    return f.read_text("utf-8")
            return ""

        def fzf(self) -> str:
            src = self.read_src().strip()
            if len(src) < 1:
                Kiritori.log("src file '{}' not found...".format(self._src_name))
                return ""
            src = "\n".join(sorted(sorted(src.splitlines()), key=len))
            try:
                cmd = ["fzf.exe", "--no-sort"]
                proc = subprocess.run(
                    cmd, input=src, capture_output=True, encoding="utf-8"
                )
                if proc.returncode != 0:
                    if o := proc.stdout:
                        Kiritori.log(o)
                    if e := proc.stderr:
                        Kiritori.log(e)
                    return ""
                return proc.stdout
            except Exception as e:
                Kiritori.log(e)
                return ""

        def get_index(self) -> str:
            idxs = []
            width = 1
            pane = CPane(window)
            reg = re.compile(r"^\d+")
            for d in pane.dirs:
                name = d.getName()
                if m := reg.match(name):
                    s = m.group(0)
                    idxs.append(int(s))
                    width = max(width, len(s))
            if len(idxs) < 1:
                return "0"
            idxs.sort()
            return str(idxs[-1] + 1).rjust(width, "0")

        def get_name(self) -> str:
            result = self.fzf().strip()
            if -1 < (i := result.find("|")):
                result = result[:i].strip()
            if result.startswith("#"):
                idx = self.get_index()
                return idx + result[1:]
            return result

    def ruled_mkdir() -> None:
        if not check_fzf():
            Kiritori.log("fzf.exe not found.")
            return

        pane = CPane(window)

        def _get_name(job_item: ckit.JobItem) -> None:
            job_item.name = ""
            dr = DirRule(pane.currentPath)
            job_item.name = dr.get_name()

        def _mkdir(job_item: ckit.JobItem) -> None:
            name = job_item.name
            if 0 < len(name):
                pane.mkdir(name)

        job = ckit.JobItem(_get_name, _mkdir)
        window.taskEnqueue(job, create_new_queue=False)

    KEYBINDER.bind("S-A-N", ruled_mkdir)

    class zyl:
        def __init__(self) -> None:
            self._exe_path = Path(USER_PROFILE, r"Personal\tools\bin\zyl.exe")
            self._src_path = Path(USER_PROFILE, r"Personal\launch.yaml")
            self._cmd = [
                str(self._exe_path),
                "-src={}".format(self._src_path),
                "-exclude=_obsolete,node_modules",
                "-stdout=True",
            ]

        def check(self) -> bool:
            for p in [self._exe_path, self._src_path]:
                if not smart_check_path(p):
                    return False
            return True

        def invoke(self, search_all: bool = False) -> Callable:
            cmd = self._cmd + ["-all={}".format(search_all)]

            def _find(job_item: ckit.JobItem) -> None:
                job_item.result = None
                if not self.check():
                    Kiritori.log("Exe not found: '{}'".format(self._exe_path))
                    return
                delay()
                proc = subprocess.run(cmd, capture_output=True, encoding="utf-8")
                result = proc.stdout.strip()
                if result:
                    if proc.returncode != 0:
                        if result:
                            Kiritori.log(result)
                        return
                    job_item.result = result

            def _open(job_item: ckit.JobItem) -> None:
                if job_item.result:
                    pane = CPane(window)
                    pane.openPath(job_item.result)

            def _wrapper() -> None:
                job = ckit.JobItem(_find, _open)
                window.taskEnqueue(job, create_new_queue=False)

            return _wrapper

    KEYBINDER.bind("C-Space", zyl().invoke())
    KEYBINDER.bind("C-S-Space", zyl().invoke(True))

    class zyw:
        def __init__(self) -> None:
            self._exe_path = Path(USER_PROFILE, r"Personal\tools\bin\zyw.exe")
            self._cmd = [
                str(self._exe_path),
                "-exclude=_obsolete,node_modules",
            ]

        def check(self) -> bool:
            return smart_check_path(self._exe_path)

        def invoke(self, search_all: bool, offset: int) -> Callable:

            def _find(job_item: ckit.JobItem) -> None:
                job_item.result = None
                if not self.check():
                    Kiritori.log("Exe not found: '{}'".format(self._exe_path))
                    return
                pane = CPane(window)
                cmd = self._cmd + [
                    "-all={}".format(search_all),
                    "-offset={}".format(offset),
                    "-src={}".format(pane.currentPath),
                ]
                delay()
                proc = subprocess.run(cmd, capture_output=True, encoding="utf-8")
                result = proc.stdout.strip()
                if result:
                    if proc.returncode != 0:
                        if result:
                            Kiritori.log(result)
                        return
                    job_item.result = result

            def _open(job_item: ckit.JobItem) -> None:
                result = job_item.result
                if result:
                    pane = CPane(window)
                    pane.openPath(result)

            def _wrapper() -> None:
                job = ckit.JobItem(_find, _open)
                window.taskEnqueue(job, create_new_queue=False)

            return _wrapper

        def apply(self, key: str) -> None:
            for alt, search_all in {"": False, "A-": True}.items():
                for shift, offset in {"": -1, "S-": 1}.items():
                    KEYBINDER.bind(alt + shift + key, self.invoke(search_all, offset))

    zyw().apply("Z")
    KEYBINDER.bind("S-F", zyw().invoke(False, 0))
    KEYBINDER.bind("C-F", zyw().invoke(True, 0))

    def concatenate_pdf() -> None:
        exe_path = os.path.join(USER_PROFILE, r"Personal\tools\bin\go-pdfconc.exe")
        if not smart_check_path(exe_path):
            return

        pane = CPane(window)
        if not pane.hasSelection:
            return
        for path in pane.selectedItemPaths:
            p = Path(path)
            if p.is_dir():
                Kiritori.log("dir item is selected!")
                return
            if p.suffix != ".pdf":
                Kiritori.log("non-pdf file found!")
                return

        basename = "conc"
        result = window.commandLine(
            title="Outname", text=basename, selection=[0, len(basename)]
        )
        if not result:
            return
        basename = result.strip()
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
                )
                if proc.returncode != 0:
                    Kiritori.log("ERROR: {}".format(proc.stdout))
            except Exception as e:
                Kiritori.log(e)

        def _finish(job_item: ckit.JobItem) -> None:
            window.clearProgress()
            if job_item.isCanceled():
                Kiritori.log("Canceled.")
            else:
                pane.refresh()
                name = basename + ".pdf"
                pane.focusByName(name)
                Kiritori.log("Concatenated as '{}':\n\n{}".format(name, src))

        job = ckit.JobItem(_conc, _finish)
        window.taskEnqueue(job, create_new_queue=False)

    def make_internet_shortcut(src: str = "") -> None:
        lines = ["[InternetShortcut]"]
        url = window.commandLine("URL", text=src)
        if not url:
            return
        if not url.startswith("http"):
            Kiritori.log("invalid url: '{}'".format(url))
            return
        lines.append("URL={}".format(url))
        title = window.commandLine("Shortcut title")
        if not title:
            return
        if not title.endswith(".url"):
            title = title + ".url"
        Path(CPane(window).currentPath, title).write_text(
            "\n".join(lines), encoding="utf-8"
        )

    def on_paste() -> None:
        c = ckit.getClipboardText()
        if len(c) < 1:
            save_clipboard_image_as_file()
            return
        if c.startswith("http"):
            make_internet_shortcut(c)
            return
        CPane(window).openPath(c.strip().strip('"'))

    KEYBINDER.bind("C-V", on_paste)

    def smart_jump_input() -> None:
        pane = CPane(window)

        current_drive = Path(pane.currentPath).drive
        wrapper = "<>"

        drives = []
        for d in ckit.getDrives():
            d += ":"
            if d != current_drive:
                detail = ckit.getDriveDisplayName(d)
                drives.append(
                    d + wrapper[0] + detail[: detail.find("(") - 1] + wrapper[-1]
                )

        def _listup_names(update_info: ckit.ckit_widget.EditWidget.UpdateInfo) -> tuple:
            found = []
            for name in drives + pane.names:
                if name.lower().startswith(update_info.text.lower()):
                    found.append(name)
            return found, 0

        result = window.commandLine(
            title="JumpInputSmart",
            auto_complete=True,
            candidate_handler=_listup_names,
        )
        if result is not None:
            result = result.strip()
            if wrapper[0] in result:
                result = result[: result.find(wrapper[0])]
            if len(result) < 1:
                return
            if ":" in result:
                pane.openPath(result)
            else:
                pane.openPath(os.path.join(pane.currentPath, result))

    KEYBINDER.bind("F", smart_jump_input)

    def smart_extract() -> None:
        active_pane = CPane(window)
        checker = ExtensionChecker(window)

        for item in active_pane.selectedItems:
            ext = Path(item.getFullpath()).suffix
            if not checker.is_archiver(ext):
                active_pane.unSelect(active_pane.byName(item.getName()))

        if len(active_pane.selectedItems) < 1:
            return

        dirname_filler = datetime.datetime.today().strftime("unzip_%Y%m%d%H%M%S")
        result = window.commandLine("Extract as", text=dirname_filler)
        if not result:
            return

        if active_pane.byName(result) != -1:
            Kiritori.log("'{}' already exists.".format(result))
            return

        active_pane.mkdir(result, False)
        extract_path = os.path.join(active_pane.currentPath, result)

        inactive_pane = CPane(window, False)
        inactive_pane.openPath(extract_path)
        window.command_ExtractArchive(None)

    KEYBINDER.bind("A-S-T", smart_extract)

    def recylcebin() -> None:
        shell_exec("shell:RecycleBinFolder")

    KEYBINDER.bind("Delete", recylcebin)

    def copy_current_path() -> None:
        pane = CPane(window)
        p = pane.currentPath
        ckit.setClipboardText(p)
        window.setStatusMessage("copied current path: '{}'".format(p), 3000)

    KEYBINDER.bind("C-A-P", copy_current_path)

    class Clipper:
        def __init__(self) -> None:
            pass

        @staticmethod
        def targets() -> List[str]:
            pane = CPane(window)
            if pane.isBlank:
                return [pane.currentPath]
            paths = []
            for i in range(pane.count):
                item = pane.byIndex(i)
                if item.selected():
                    paths.append(item.getFullpath())
                    pane.unSelect(i)
            if len(paths) < 1:
                paths.append(pane.focusedItemPath)
            return paths

        @staticmethod
        def toClipboard(ss: List[str]) -> None:
            if check_log_selected():
                window.command_SetClipboard_LogSelected(None)
                return
            if 0 < len(ss):
                ckit.setClipboardText("\n".join(ss))
                if len(ss) == 1:
                    window.setStatusMessage("Copied: '{}'".format(ss[0]), 2000)
                    return

                def _func() -> None:
                    print("Copied:")
                    for s in ss:
                        print("- '{}'".format(s))

                Kiritori.wrap(_func)

        @classmethod
        def paths(cls) -> None:
            paths = cls.targets()
            cls.toClipboard(paths)

        @classmethod
        def names(cls) -> None:
            paths = cls.targets()
            names = [Path(path).name for path in paths]
            cls.toClipboard(names)

        @classmethod
        def basenames(cls) -> None:
            paths = cls.targets()
            basenames = [Path(path).stem for path in paths]
            cls.toClipboard(basenames)

    KEYBINDER.bind("C-C", Clipper().paths)
    KEYBINDER.bind("C-S-C", Clipper().names)
    KEYBINDER.bind("C-S-B", Clipper().basenames)

    class Selector:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

        @property
        def pane(self) -> CPane:
            return CPane(self._window)

        def allItems(self) -> None:
            pane = self.pane
            pane.selectAll()

        def clear(self) -> None:
            pane = self.pane
            pane.unSelect(pane.cursor)

        def toggleAll(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                pane.toggleSelection(i)

        def toTop(self) -> None:
            pane = self.pane
            if pane.cursor < pane.selectionTop:
                for i in range(pane.count):
                    if i <= pane.cursor:
                        pane.select(i)
            else:
                for item in pane.selectedOrAllItems:
                    i = pane.byName(item.getName())
                    if i <= pane.cursor:
                        pane.toggleSelection(i)

        def clearToTop(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if i <= pane.cursor:
                    pane.unSelect(i)

        def toBottom(self) -> None:
            pane = self.pane
            if pane.selectionBottom < pane.cursor:
                for i in range(pane.count):
                    if pane.cursor <= i:
                        pane.select(i)
            else:
                for item in pane.selectedOrAllItems:
                    i = pane.byName(item.getName())
                    if pane.cursor <= i:
                        pane.toggleSelection(i)

        def clearToBottom(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if pane.cursor < i:
                    pane.unSelect(i)

        def files(self) -> None:
            pane = self.pane
            for item in pane.selectedOrAllItems:
                name = item.getName()
                if not item.isdir():
                    pane.toggleSelection(pane.byName(name))

        def dirs(self) -> None:
            pane = self.pane
            for item in pane.selectedOrAllItems:
                name = item.getName()
                if item.isdir():
                    pane.toggleSelection(pane.byName(name))

        def clearAll(self) -> None:
            pane = self.pane
            pane.unSelectAll()

        def byFunction(self, func: Callable, negative: bool = False) -> None:
            pane = self.pane
            for item in pane.selectedOrAllItems:
                path = item.getFullpath()
                if (negative and not func(path)) or (not negative and func(path)):
                    name = item.getName()
                    pane.toggleSelection(pane.byName(name))

        def byExtension(self, s: str, negative: bool = False) -> None:
            def _checkPath(path: str) -> bool:
                return Path(path).suffix == s

            self.byFunction(_checkPath, negative)

        def stemContains(self, s: str, negative: bool = False) -> None:
            def _checkPath(path: str) -> bool:
                return s in Path(path).stem

            self.byFunction(_checkPath, negative)

        def stemStartsWith(self, s: str, negative: bool = False) -> None:
            def _checkPath(path: str) -> bool:
                return Path(path).stem.startswith(s)

            self.byFunction(_checkPath, negative)

        def stemEndsWith(self, s: str, negative: bool = False) -> None:
            def _checkPath(path: str) -> bool:
                return Path(path).stem.endswith(s)

            self.byFunction(_checkPath, negative)

        def stemMatches(self, s: str, case: bool, negative: bool = False) -> None:
            reg = re.compile(s) if case else re.compile(s, re.IGNORECASE)

            def _checkPath(path: str) -> bool:
                return reg.search(Path(path).stem) is not None

            self.byFunction(_checkPath, negative)

        def apply(self) -> None:
            for k, v in {
                "C-A": self.allItems,
                "U": self.clearAll,
                "A-F": self.files,
                "A-D": self.dirs,
                "S-Home": self.toTop,
                "S-A": self.toTop,
                "S-End": self.toBottom,
                "S-E": self.toBottom,
            }.items():
                KEYBINDER.bind(k, v)

    Selector(window).apply()

    def unselect_panes() -> None:
        CPane(window).unSelectAll()
        CPane(window, False).unSelectAll()

    KEYBINDER.bind("C-U", unselect_panes)

    class SmartJumper:
        def __init__(self, window: MainWindow) -> None:
            self._pane = CPane(window)

        @staticmethod
        def getBlockEdges(idxs: List[int]) -> List[int]:
            if len(idxs) < 1:
                return []

            edges = []
            start = idxs[0]
            end = start

            for idx in idxs[1:]:
                if idx == end + 1:
                    end = idx
                else:
                    edges.append(start)
                    edges.append(end)
                    start = idx
                    end = idx

            edges.append(start)
            if 0 < len(edges) and edges[-1] != end:
                edges.append(end)
            return edges

        @property
        def jumpable(self) -> List[int]:
            pane = self._pane
            if pane.isBlank:
                return []
            stack = []
            for i in range(pane.count):
                item = self._pane.byIndex(i)
                if item.bookmark() or item.selected():
                    stack.append(i)
            stack = self.getBlockEdges(stack)
            stack.append(0)
            stack.append(pane.count - 1)
            if 0 < (nd := len(pane.dirs)):
                stack.append(nd - 1)
                if 0 < len(pane.files):
                    stack.append(nd)
            return sorted(list(set(stack)))

        def down(self, selecting: bool) -> None:
            targets = self.jumpable
            if len(targets) < 1:
                return
            pane = self._pane
            cur = pane.cursor
            idx = -1
            for t in targets:
                if cur < t:
                    idx = t
                    break
            if idx < 0:
                return
            if selecting:
                for i in range(pane.count):
                    if cur <= i and i <= idx:
                        pane.select(i)
            pane.focus(idx)

        def up(self, selecting: bool) -> None:
            targets = self.jumpable
            if len(targets) < 1:
                return
            pane = self._pane
            cur = pane.cursor
            idx = -1
            for t in targets:
                if t < cur:
                    idx = t
            if idx < 0:
                return
            if selecting:
                for i in range(pane.count):
                    if idx <= i and i <= cur:
                        pane.select(i)
            pane.focus(idx)

    def smart_jumpDown(selecting: bool = False) -> Callable:
        def _jumper() -> None:
            SmartJumper(window).down(selecting)

        return _jumper

    KEYBINDER.bind("C-J", smart_jumpDown(False))
    KEYBINDER.bind("C-Down", smart_jumpDown(False))
    KEYBINDER.bind("S-C-J", smart_jumpDown(True))
    KEYBINDER.bind("S-C-Down", smart_jumpDown(True))

    def smart_jumpUp(selecting: bool = False) -> None:
        def _jumper() -> None:
            SmartJumper(window).up(selecting)

        return _jumper

    KEYBINDER.bind("C-K", smart_jumpUp(False))
    KEYBINDER.bind("C-Up", smart_jumpUp(False))
    KEYBINDER.bind("S-C-K", smart_jumpUp(True))
    KEYBINDER.bind("S-C-Up", smart_jumpUp(True))

    def duplicate_pane() -> None:
        window.command_ChdirInactivePaneToOther(None)
        pane = CPane(window)
        pane.focusOther()

    KEYBINDER.bind("W", duplicate_pane)
    KEYBINDER.bind("D", duplicate_pane)

    def open_on_explorer() -> None:
        pane = CPane(window, True)
        shell_exec(pane.currentPath)

    KEYBINDER.bind("C-S-E", open_on_explorer)

    def open_to_other() -> None:
        active_pane = CPane(window, True)
        inactive_pane = CPane(window, False)
        inactive_pane.openPath(active_pane.focusedItemPath)
        active_pane.focusOther()

    KEYBINDER.bind("S-L", open_to_other)

    def open_parent_to_other() -> None:
        active_pane = CPane(window, True)
        parent = str(Path(active_pane.currentPath).parent)
        current_name = str(Path(active_pane.currentPath).name)
        inactive_pane = CPane(window, False)
        inactive_pane.openPath(parent, current_name)
        active_pane.focusOther()

    KEYBINDER.bind("S-U", open_parent_to_other)

    def on_vscode() -> None:
        vscode_path = Path(USER_PROFILE, r"scoop\apps\vscode\current\Code.exe")
        if smart_check_path(vscode_path):
            pane = CPane(window)
            shell_exec(str(vscode_path), pane.currentPath)

    KEYBINDER.bind("V", on_vscode)

    class Renamer:
        def __init__(self, window: MainWindow) -> None:
            self._window = window
            self._pane = CPane(self._window)

        @staticmethod
        def renamable(item) -> bool:
            return (
                hasattr(item, "rename")
                and hasattr(item, "utime")
                and hasattr(item, "uattr")
            )

        @property
        def candidate(self) -> list:
            if self._pane.hasSelection:
                items = []
                for item in self._pane.selectedItems:
                    if self.renamable(item):
                        items.append(item)
                return items
            item = self._pane.focusedItem
            if self.renamable(item):
                return [item]
            return []

        def execute(self, org_path: Path, new_name: str, focus: bool = False) -> None:
            new_path = org_path.with_name(new_name)
            if smart_check_path(new_path):
                if new_path.name in [c.name for c in new_path.parent.iterdir()]:
                    print("'{}' already exists!".format(new_name))
                    return
            try:
                self._window.subThreadCall(org_path.rename, (str(new_path),))
                print("Renamed: {}\n     ==> {}\n".format(org_path.name, new_name))
                self._pane.refresh()
                if focus:
                    self._pane.focusByName(new_name)
            except Exception as e:
                print(e)

    def rename_substr() -> None:
        renamer = Renamer(window)

        targets = renamer.candidate
        if len(targets) < 1:
            return

        print("Rename substring:")
        result = window.commandLine("Offset[;Length]")

        if not result:
            print("Canceled.\n")
            return

        sep = ";"

        def _get_offset() -> int:
            if sep in result:
                if result.startswith(sep):
                    return 0
                return int(result[: result.find(sep)])
            return int(result)

        def _get_length() -> int:
            if sep in result:
                if result.endswith(sep):
                    return 0
                return int(result[result.rfind(sep) + 1 :])
            return 0

        offset = _get_offset()
        length = _get_length()

        class RenameInfo(NamedTuple):
            orgPath: Path
            newName: str

        def _confirm() -> List[RenameInfo]:
            infos = []
            lines = []
            for item in targets:
                org_path = Path(item.getFullpath())
                stem = org_path.stem
                new_name = stem[:offset]
                if 0 < length:
                    new_name += stem[offset + length :]
                new_name += org_path.suffix

                infos.append(RenameInfo(org_path, new_name))
                lines.append("Rename: {}\n    ==> {}\n".format(org_path.name, new_name))

            lines.append(
                "\noffset: {}\nlength: {}\nOK? (Enter / Esc)".format(offset, length)
            )

            if not popResultWindow(window, "Preview", "\n".join(lines)):
                return []
            return infos

        infos = _confirm()
        if len(infos) < 1:
            print("Canceled.\n")
            return

        def _func() -> None:
            for info in infos:
                renamer.execute(info.orgPath, info.newName)

        Kiritori.wrap(_func)

    KEYBINDER.bind("S-S", rename_substr)

    def rename_extension() -> None:
        pane = CPane(window)
        renamer = Renamer(window)
        item = pane.focusedItem
        if not renamer.renamable(item) or pane.isBlank:
            return
        focus_path = Path(item.getFullpath())
        org_ext = focus_path.suffix
        new_ext, mod = window.commandLine(
            title="New Extension", text=org_ext[1:], return_modkey=True
        )
        if not new_ext:
            return
        new_ext = new_ext.strip()
        if len(new_ext) < 1:
            return
        if new_ext.startswith("."):
            new_ext = new_ext[1:]
        new_name = focus_path.stem + "." + new_ext

        def _func() -> None:
            renamer.execute(focus_path, new_name, mod == ckit.MODKEY_SHIFT)

        Kiritori.wrap(_func)

    KEYBINDER.bind("A-X", rename_extension)

    def rename_insert() -> None:
        renamer = Renamer(window)

        targets = renamer.candidate
        if len(targets) < 1:
            return

        print("Rename insert (reversable with shift-enter):")
        result, mod = window.commandLine("Text[@position]", return_modkey=True)

        if not result:
            print("Canceled.\n")
            return

        sep = "@"

        def _get_insert_text() -> str:
            if sep in result:
                if result.endswith(sep):
                    return result[:-1]
                return result[: result.rfind(sep)]
            return result

        def _get_insert_pos() -> Union[int, None]:
            if sep in result:
                if result.endswith(sep):
                    return None
                return int(result[result.rfind(sep) + 1 :])
            return None

        ins = _get_insert_text()
        pos = _get_insert_pos()
        reverse = mod == ckit.MODKEY_SHIFT

        class RenameInfo(NamedTuple):
            orgPath: Path
            newName: str

        def _confirm() -> List[RenameInfo]:
            infos = []
            lines = []
            for item in targets:
                org_path = Path(item.getFullpath())

                def _get_new_name() -> str:
                    if pos is None:
                        return org_path.stem + ins + org_path.suffix
                    stem = org_path.stem
                    i = pos * -1 if reverse else pos
                    return stem[:i] + ins + stem[i:] + org_path.suffix

                new_name = _get_new_name()
                infos.append(RenameInfo(org_path, new_name))
                lines.append("Rename: {}\n    ==> {}\n".format(org_path.name, new_name))

            lines.append("\ninsert: {}\nat: {}\nOK? (Enter / Esc)".format(ins, pos))

            if not popResultWindow(window, "Preview", "\n".join(lines)):
                return []
            return infos

        infos = _confirm()
        if len(infos) < 1:
            print("Canceled.\n")
            return

        def _func() -> None:
            for info in infos:
                renamer.execute(info.orgPath, info.newName)

        Kiritori.wrap(_func)

    KEYBINDER.bind("S-I", rename_insert)

    class Suffixer:
        sep = "_"

        def __init__(
            self, window: MainWindow, include_ext: bool, with_timestamp: bool = False
        ) -> None:
            pane = CPane(window)
            self.timestamp = ""
            if with_timestamp:
                self.timestamp = datetime.datetime.today().strftime("%Y%m%d")
            self.names = []
            for name in pane.names:
                if self.sep not in name or name.startswith(self.sep):
                    continue
                p = Path(pane.currentPath, name)
                if include_ext:
                    self.names.append(p.name)
                else:
                    self.names.append(p.stem)

        @property
        def possible_suffix(self) -> List[str]:
            sufs = []
            for name in self.names:
                for i, c in enumerate(name):
                    if c == self.sep:
                        sufs.append(name[i:])
            sufs = sorted(list(set(sufs)), key=len)
            if self.timestamp:
                sufs = [self.sep + self.timestamp] + sufs
            return sufs

        def candidates(self, s: str) -> List[str]:
            sufs = self.possible_suffix
            if self.sep not in s:
                return [s + suf for suf in sufs]
            if s.endswith(self.sep):
                return [s + suf[1:] for suf in sufs]
            found = []
            suffix_from_command = s[s.find(self.sep) :]
            for suf in sufs:
                if suf.startswith(suffix_from_command):
                    suffix_rest = suf[len(suffix_from_command) :]
                    found.append(s + suffix_rest)
            return found

        def __call__(
            self, update_info: ckit.ckit_widget.EditWidget.UpdateInfo
        ) -> Tuple[List[str], int]:
            return self.candidates(update_info.text), 0

    def invoke_renamer(append: bool) -> Callable:
        def _renamer() -> None:
            pane = CPane(window)
            renamer = Renamer(window)
            item = pane.focusedItem
            if not renamer.renamable(item) or pane.isBlank:
                return

            org_path = Path(item.getFullpath())
            offset = len(org_path.stem)
            o = offset if append else 0
            sel = [o, o]

            new_stem, mod = window.commandLine(
                title="NewStem",
                text=org_path.stem,
                selection=sel,
                candidate_handler=Suffixer(window, False, True),
                return_modkey=True,
            )

            if not new_stem:
                return

            new_name = new_stem + org_path.suffix

            def _func() -> None:
                renamer.execute(org_path, new_name, mod == ckit.MODKEY_SHIFT)

            Kiritori.wrap(_func)

        return _renamer

    KEYBINDER.bind("N", invoke_renamer(True))
    KEYBINDER.bind("S-N", invoke_renamer(False))

    def duplicate_file(only_stem: bool) -> None:
        pane = CPane(window)

        src_path = Path(pane.focusedItemPath)
        if pane.hasSelection:
            if 1 < len(pane.selectedItems):
                Kiritori.log("Caneled. (Select nothing or just 1 item)")
                return
            src_path = Path(pane.selectedItemPaths[0])

        sel_end = len(src_path.stem) if only_stem else len(src_path.name)
        sel_start = src_path.stem.rfind("_")
        if sel_start < 0:
            sel_start = sel_end
        prompt = "NewStem" if only_stem else "NewName"
        placeholder = src_path.stem if only_stem else src_path.name
        result = window.commandLine(
            title=prompt,
            text=placeholder,
            candidate_handler=Suffixer(window, (not only_stem), True),
            selection=[sel_start, sel_end],
        )

        if result:
            result = result.strip()
            if len(result) < 1:
                return
            if src_path.is_file() and only_stem:
                result = result + src_path.suffix
            new_path = src_path.with_name(result)

            if smart_check_path(new_path):
                Kiritori.log("Canceled. (Same item exists)")
                return

            def _copy_as(new_path: str) -> None:
                if Path(src_path).is_dir():
                    shutil.copytree(src_path, new_path)
                else:
                    shutil.copy(src_path, new_path)

            window.subThreadCall(_copy_as, (new_path,))
            pane.refresh()
            pane.focusByName(Path(new_path).name)

    KEYBINDER.bind("S-D", lambda: duplicate_file(True))
    KEYBINDER.bind("A-S-D", lambda: duplicate_file(False))

    def smart_move_to_dir(remove_origin: bool) -> None:
        prompt = "MoveTo" if remove_origin else "CopyTo"

        def _mover() -> None:
            pane = CPane(window)

            items = []
            for item in pane.selectedItems:
                if hasattr(item, "delete"):
                    items.append(item)

            if len(items) < 1:
                return

            possible_dests = []
            names = [item.getName() for item in items]
            for d in pane.dirs:
                if (dn := d.getName()) not in names:
                    possible_dests.append(dn)

            def _listup_dests(
                update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
            ) -> tuple:
                found = [dd for dd in possible_dests if dd.startswith(update_info.text)]
                return found, 0

            result, mod = window.commandLine(
                prompt,
                auto_complete=True,
                candidate_handler=_listup_dests,
                return_modkey=True,
            )
            if not result:
                return

            dir_path = Path(pane.currentPath, result)
            if not smart_check_path(dir_path):
                pane.mkdir(result)
            pane.copyToChild(result, items, remove_origin)
            if mod == ckit.MODKEY_SHIFT:
                pane.openPath(str(dir_path))
            else:
                pane.focusByName(result)

        return _mover

    KEYBINDER.bind("A-M", smart_move_to_dir(True))
    KEYBINDER.bind("A-C", smart_move_to_dir(False))

    def smart_mkdir() -> None:
        pane = CPane(window)
        ts = datetime.datetime.today().strftime("%Y%m%d")
        result, mod = window.commandLine(
            "DirName",
            text=ts,
            selection=[0, len(ts)],
            candidate_handler=Suffixer(window, False, False),
            return_modkey=True,
        )
        if not result:
            return
        dirname = result.strip()
        if len(dirname) < 1:
            return
        pane.mkdir(result)
        if mod == ckit.MODKEY_SHIFT:
            pane.openChild(dirname)

    KEYBINDER.bind("C-S-N", smart_mkdir)

    class Toucher:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

        def invoke(self, extension: str = "") -> None:
            def _func() -> None:
                pane = CPane(self._window)
                if not hasattr(pane.fileList.getLister(), "touch"):
                    return

                prompt = "NewFileName"
                suffix = "." + extension if 0 < len(extension) else ""
                if suffix:
                    prompt += " ({})".format(suffix)
                else:
                    prompt += " (with extension)"
                result, mod = window.commandLine(
                    prompt,
                    candidate_handler=Suffixer(window, len(extension) < 1, True),
                    return_modkey=True,
                )
                if not result:
                    return
                filename = result.strip()
                if len(filename) < 1:
                    return

                if suffix and not filename.endswith(suffix):
                    filename += suffix
                new_path = os.path.join(pane.currentPath, filename)
                if smart_check_path(new_path):
                    Kiritori.log("'{}' already exists.".format(filename))
                    return
                pane.touch(filename)
                if mod == ckit.MODKEY_SHIFT:
                    shell_exec(new_path)

            return _func

    TOUCHER = Toucher(window)

    KEYBINDER.bind("T", TOUCHER.invoke("txt"))
    KEYBINDER.bind("A-T", TOUCHER.invoke("md"))
    KEYBINDER.bind("C-N", TOUCHER.invoke(""))

    def to_obsolete_dir() -> None:
        pane = CPane(window)

        items = []
        for i in range(pane.count):
            item = pane.byIndex(i)
            if item.selected() and hasattr(item, "delete"):
                items.append(item)
        count = len(items)
        if count < 1:
            return

        dest_name = "_obsolete"
        if pane.byName(dest_name) < 0:
            pane.mkdir(dest_name, False)
        pane.copyToChild(dest_name, items, True)

        msg = "moving {} item".format(count)
        if 1 < count:
            msg += "s"
        msg += " to '{}'".format(dest_name)
        Kiritori.log(msg)

    KEYBINDER.bind("A-O", to_obsolete_dir)

    class Rect(NamedTuple):
        left: int
        top: int
        right: int
        bottom: int

    def to_home_position(force: bool) -> None:
        hwnd = window.getHWND()
        wnd = pyauto.Window.fromHWND(hwnd)
        rect = Rect(*wnd.getRect())
        infos = pyauto.Window.getMonitorInfo()
        if force or len(infos) == 1:
            info = infos[1] if infos[0][2] != 1 and 1 < len(infos) else infos[0]
            visible_rect = Rect(*info[1])
            if (
                force
                or visible_rect.right <= rect.left
                or rect.right <= visible_rect.left
                or rect.bottom <= visible_rect.top
                or visible_rect.bottom <= rect.top
            ):
                if wnd.isMaximized():
                    wnd.restore()
                left = (visible_rect.right - visible_rect.left) // 2
                wnd.setRect([left, 0, visible_rect.right, visible_rect.bottom])
        window.command_MoveSeparatorCenter(None)
        LeftPane(window).activate()

    KEYBINDER.bind("C-0", lambda: to_home_position(True))

    def reload_config() -> None:
        window.configure()
        window.reloadTheme()
        to_home_position(False)
        ts = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S.%f")
        window.setStatusMessage("reloaded config.py | {}".format(ts), 2000)

    KEYBINDER.bind("C-R", reload_config)
    KEYBINDER.bind("F5", reload_config)

    def starting_position(both_pane: bool = False) -> None:
        window.command_MoveSeparatorCenter(None)
        desktop_path = os.path.join(USER_PROFILE, "Desktop")
        pane = CPane(window, True)
        if pane.currentPath != desktop_path:
            pane.openPath(desktop_path)
        if both_pane:
            window.command_ChdirInactivePaneToOther(None)
            LeftPane(window).activate()

    KEYBINDER.bind("0", lambda: starting_position(False))
    KEYBINDER.bind("S-0", lambda: starting_position(True))

    def open_doc() -> None:
        help_path = os.path.join(ckit.getAppExePath(), "doc", "index.html")
        shell_exec(help_path)

    KEYBINDER.bind("A-H", open_doc)

    def edit_config() -> None:
        config_dir = os.path.join(os.environ.get("APPDATA"), "CraftFiler")
        if not smart_check_path(config_dir):
            Kiritori.log("cannot find config dir: {}".format(config_dir))
            return
        dir_path = config_dir
        if (real_path := os.path.realpath(config_dir)) != config_dir:
            dir_path = os.path.dirname(real_path)
        vscode_path = os.path.join(USER_PROFILE, r"scoop\apps\vscode\current\Code.exe")
        if smart_check_path(vscode_path):
            shell_exec(vscode_path, dir_path)
        else:
            shell_exec(dir_path)

    KEYBINDER.bind("C-E", edit_config)

    class ClonedItem(NamedTuple):
        origin: str
        clones: list

    class ClonedItems:
        _items: List[ClonedItem]

        def __init__(self) -> None:
            self._items = []

        def register(self, origin: str, clones: list) -> None:
            c = ClonedItem(origin, clones)
            self._items.append(c)

        @staticmethod
        def count_bytes(s: str) -> int:
            n = 0
            for c in s:
                if unicodedata.east_asian_width(c) in "FWA":
                    n += 2
                else:
                    n += 1
            return n

        @property
        def names(self) -> List[str]:
            return [item.origin for item in self._items]

        def get_max_width(self) -> int:
            width = 0
            for name in self.names:
                bn = self.count_bytes(name)
                width = max(width, bn)
            return width + 2

        def show(self) -> None:
            buffer_width = self.get_max_width()
            for item in self._items:
                name = item.origin
                for i, n in enumerate(item.clones):
                    w = self.count_bytes(name)
                    if i == 0:
                        filler = "=" * (buffer_width - w)
                        print(name, filler, n)
                    else:
                        filler = " " * w + "=" * (buffer_width - w)
                        print("", filler, n)

    class ItemsDiff:
        _active_pane: CPane
        _inactive_pane: CPane

        def __init__(self) -> None:
            self._active_pane = CPane(window, True)
            self._inactive_pane = CPane(window, False)

        @staticmethod
        def to_hash(path: str) -> str:
            mb = 1024 * 1024
            read_size = 1 * mb if 5 * mb < os.path.getsize(path) else None
            with open(path, "rb") as f:
                digest = hashlib.md5(f.read(read_size)).hexdigest()
            return digest

        @property
        def targets(self) -> list:
            if self._active_pane.hasSelection:
                items = []
                for item in self._active_pane.selectedItems:
                    if not item.isdir():
                        items.append(item)
                return items
            return self._active_pane.files

        def unselect_inactive_pane(self) -> None:
            for i in range(self._inactive_pane.count):
                self._inactive_pane.unSelect(i)

        def compare(self) -> None:
            def _scan(job_item: ckit.JobItem) -> None:
                targets = self.targets

                job_item.comparable = 0 < len(targets)
                if not job_item.comparable:
                    return

                Kiritori.log("comparing md5 hash")

                window.setProgressValue(None)

                table = {}
                for path in self._inactive_pane.traverse():
                    if job_item.isCanceled():
                        return
                    rel = Path(path).relative_to(self._inactive_pane.currentPath)
                    digest = self.to_hash(path)
                    table[digest] = table.get(digest, []) + [str(rel)]

                self.unselect_inactive_pane()
                compare_with_selected_items = self._active_pane.hasSelection
                cloned_items = ClonedItems()

                for file in targets:
                    if job_item.isCanceled():
                        return
                    digest = self.to_hash(file.getFullpath())
                    if digest in table:
                        name = file.getName()
                        if not compare_with_selected_items:
                            self._active_pane.selectByName(name)
                        cloned_items.register(name, table[digest])

                        for n in table[digest]:
                            self._inactive_pane.selectByName(n)

                cloned_items.show()

            def _finish(job_item: ckit.JobItem) -> None:
                window.clearProgress()
                if job_item.comparable:
                    if job_item.isCanceled():
                        Kiritori.log("Canceled.")
                    else:
                        Kiritori.log("finished")
                else:
                    Kiritori.log("finished (nothing to compare)")

            job = ckit.JobItem(_scan, _finish)
            window.taskEnqueue(job, create_new_queue=False)

    def find_same_file() -> None:
        ItemsDiff().compare()

    def diffinity() -> None:
        exe_path = Path(USER_PROFILE, r"scoop\apps\diffinity\current\Diffinity.exe")
        if not smart_check_path(exe_path):
            Kiritori.log("cannnot find diffinity.exe...")
            return

        left_pane = LeftPane(window)
        left_selcted = left_pane.selectedItemPaths
        if len(left_selcted) != 1:
            Kiritori.log("select just 1 file on left pane.")
            return
        left_path = Path(left_selcted[0])
        if not left_path.is_file():
            Kiritori.log("selected item on left pane is not comparable.")
            return
        left_pane = LeftPane(window)

        right_pane = RightPane(window)
        right_selcted = right_pane.selectedItemPaths
        if len(right_selcted) != 1:
            Kiritori.log("select just 1 file on right pane.")
            return
        right_path = Path(right_selcted[0])
        if not right_path.is_file():
            Kiritori.log("selected item on right pane is not comparable.")
            return

        shell_exec(exe_path, str(left_path), str(right_path))

    def from_inactive_names() -> None:
        pane = CPane(window)
        pane.unSelectAll()
        active_names = pane.names
        inactive = CPane(window, False)
        inactive_names = [item.getName() for item in inactive.selectedOrAllItems]
        for name in active_names:
            if name in inactive_names:
                pane.selectByName(name)

    def from_active_names() -> None:
        pane = CPane(window)
        active_names = [item.getName() for item in pane.selectedOrAllItems]
        inactive = CPane(window, False)
        inactive.unSelectAll()
        inactive_names = inactive.names
        for name in inactive_names:
            if name in active_names:
                inactive.selectByName(name)

    def invoke_regex_selector(case: bool) -> Callable:
        def _selector() -> None:
            result, mod = window.commandLine("Regexp", return_modkey=True)

            if result:
                Selector(window).stemMatches(result, case, mod == ckit.MODKEY_SHIFT)

        return _selector

    KEYBINDER.bind("S-Colon", invoke_regex_selector(True))

    def select_same_name() -> None:
        pane = CPane(window)
        active_names = pane.selectedItemNames
        if len(active_names) < 1:
            active_names = [pane.focusedItem.getName()]
        inactive = CPane(window, False)
        inactive.unSelectAll()

        for name in inactive.names:
            if name in active_names:
                inactive.selectByName(name)

    def select_name_common() -> None:
        pane = CPane(window)
        pane.unSelectAll()
        active_names = pane.names
        inactive = CPane(window, False)
        inactive.unSelectAll()
        inactive_names = inactive.names

        for name in active_names:
            if name in inactive_names:
                pane.selectByName(name)
        for name in inactive_names:
            if name in active_names:
                inactive.selectByName(name)

    def select_name_unique() -> None:
        pane = CPane(window)
        pane.unSelectAll()
        active_names = pane.names
        inactive = CPane(window, False)
        inactive.unSelectAll()
        inactive_names = inactive.names

        for name in active_names:
            if name not in inactive_names:
                pane.selectByName(name)
        for name in inactive_names:
            if name not in active_names:
                inactive.selectByName(name)

    def select_stem_startswith() -> None:
        pane = CPane(window)
        stem = Path(pane.focusedItemPath).stem
        last_sep = stem.rfind("_")
        t = stem[: last_sep + 1]

        c = [len(t)] * 2
        result, mod = window.commandLine(
            "StartsWith", return_modkey=True, text=t, selection=c
        )
        if result:
            Selector(window).stemStartsWith(result, mod == ckit.MODKEY_SHIFT)

    KEYBINDER.bind("Caret", select_stem_startswith)

    def select_stem_endswith() -> None:
        pane = CPane(window)
        stem = Path(pane.focusedItemPath).stem
        first_sep = stem.find("_")
        t = stem[first_sep:]

        result, mod = window.commandLine(
            "EndsWith", return_modkey=True, text=t, selection=[0, 0]
        )
        if result:
            Selector(window).stemEndsWith(result, mod == ckit.MODKEY_SHIFT)

    KEYBINDER.bind("S-4", select_stem_endswith)

    def select_stem_contains() -> None:
        result, mod = window.commandLine("Contains", return_modkey=True)
        if result:
            Selector(window).stemContains(result, mod == ckit.MODKEY_SHIFT)

    KEYBINDER.bind("Colon", select_stem_contains)

    def select_byext() -> None:
        pane = CPane(window)
        exts = []
        for item in pane.selectedOrAllItems:
            ext = Path(item.getFullpath()).suffix
            if ext and ext not in exts:
                exts.append(ext)

        if len(exts) < 1:
            return

        exts.sort()

        sel = 0
        if (cur := Path(pane.focusedItemPath).suffix) in exts:
            sel = exts.index(cur)

        result, mod = invoke_listwindow(window, "Select Extension", exts, sel)

        if result < 0:
            return

        Selector(window).byExtension(exts[result], mod == ckit.MODKEY_SHIFT)

    KEYBINDER.bind("S-X", select_byext)

    class PseudoVoicing:
        def __init__(self, s) -> None:
            self._formatted = s
            self._voicables = "かきくけこさしすせそたちつてとはひふへほカキクケコサシスセソタチツテトハヒフヘホ"

        def _replace(self, s: str, offset: int) -> str:
            c = s[0]
            if c not in self._voicables:
                return s
            if offset == 1:
                if c == "う":
                    return "\u3094"
                if c == "ウ":
                    return "\u30f4"
            return chr(ord(c) + offset)

        def fix_voicing(self) -> None:
            self._formatted = re.sub(
                r".[\u309b\u3099]",
                lambda mo: self._replace(mo.group(0), 1),
                self._formatted,
            )

        def fix_half_voicing(self) -> None:
            self._formatted = re.sub(
                r".[\u309a\u309c]",
                lambda mo: self._replace(mo.group(0), 2),
                self._formatted,
            )

        @property
        def formatted(self) -> str:
            return self._formatted

    def rename_pseudo_voicing() -> None:
        pane = CPane(window)
        renamer = Renamer(window)
        items = pane.selectedItems
        for item in items:
            if not renamer.renamable(item):
                continue
            name = item.getName()
            pv = PseudoVoicing(name)
            pv.fix_voicing()
            pv.fix_half_voicing()
            new_name = pv.formatted
            org_path = Path(item.getFullpath())
            renamer.execute(org_path, new_name)

    def save_clipboard_image_as_file() -> None:
        pane = CPane(window)

        def _save(job_item: ckit.JobItem) -> None:
            job_item.file_name = ""
            img = ImageGrab.grabclipboard()
            if not img or isinstance(img, list):
                Kiritori.log("Canceled: No image in clipboard.")
                return
            job_item.file_name = (
                datetime.datetime.today().strftime("%Y%m%d-%H%M%S") + ".png"
            )
            save_path = os.path.join(pane.currentPath, job_item.file_name)
            img.save(save_path)

        def _finish(job_item: ckit.JobItem) -> None:
            if job_item.file_name:
                pane.refresh()
                pane.focusByName(job_item.file_name)

        job = ckit.JobItem(_save, _finish)
        window.taskEnqueue(job, create_new_queue=False)

    KEYBINDER.bind("C-S-I", save_clipboard_image_as_file)

    class PathMatchFilter:
        def __init__(self, root: str, names: List[str]) -> None:
            self.root = root
            self.names = names

        def __call__(self, item) -> bool:
            path = item.getFullpath()
            if path.startswith(self.root) and len(self.root) < len(path):
                for name in self.names:
                    p = os.path.join(self.root, name)
                    if path.startswith(p):
                        return True
                return False
            return True

        def __str__(self) -> str:
            return "[FILTERING]"

    def hide_unselected() -> None:
        pane = CPane(window)
        if pane.hasSelection:
            names = pane.selectedItemNames
            window.subThreadCall(
                pane.fileList.setFilter, (PathMatchFilter(pane.currentPath, names),)
            )
            pane.refresh()
            pane.focus(0)
            pane.repaint(PO.Focused)

    def clear_filter() -> None:
        pane = CPane(window)
        window.subThreadCall(pane.fileList.setFilter, (filter_Default("*"),))
        pane.refresh()
        pane.repaint(PO.Focused)

    KEYBINDER.bind("Q", clear_filter)

    def make_junction() -> None:
        active_pane = CPane(window)
        if not active_pane.hasSelection:
            return

        inactive_pane = CPane(window, False)
        dest = inactive_pane.currentPath
        for src_path in active_pane.selectedItemPaths:
            junction_path = Path(dest, Path(src_path).name)
            if smart_check_path(junction_path):
                Kiritori.log("'{}' already exists.".format(junction_path))
                return
            try:
                cmd = ["cmd", "/c", "mklink", "/J", str(junction_path), src_path]
                proc = subprocess.run(cmd, capture_output=True, encoding="cp932")
                result = proc.stdout.strip()
                Kiritori.log(result)
            except Exception as e:
                Kiritori.log(e)
                return

    def bookmark_here() -> None:
        path = CPane(window).currentPath
        bookmarks = [p for p in window.bookmark.getItems()]
        if path in bookmarks:
            window.bookmark.remove(path)
            Kiritori.log("Removed from bookmark: '{}'".format(path))
        else:
            window.bookmark.append(path)
            Kiritori.log("Bookmarked: '{}'".format(path))

    def reset_hotkey() -> None:
        window.ini.set("HOTKEY", "activate_vk", "0")
        window.ini.set("HOTKEY", "activate_mod", "0")

    def update_command_list(command_table: dict) -> None:
        for name, func in command_table.items():
            window.launcher.command_list += [(name, Keybinder.wrap(func))]

    update_command_list(
        {
            "SetBookmarkAlias": set_bookmark_alias,
            "BookmarkHere": bookmark_here,
            "DocxToTxt": docx_to_txt,
            "ConcPdfGo": concatenate_pdf,
            "MakeJunction": make_junction,
            "ResetHotkey": reset_hotkey,
            "ExtractZipSmart": smart_extract,
            "HideUnselectedItems": hide_unselected,
            "ClearFilter": clear_filter,
            "Diffinity": diffinity,
            "MakeInternetShortcut": lambda: make_internet_shortcut(
                ckit.getClipboardText().strip()
            ),
            "RenamePseudoVoicing": rename_pseudo_voicing,
            "FindSameFile": find_same_file,
            "FromInactiveNames": from_inactive_names,
            "FromActiveNames": from_active_names,
            "SelectSameName": select_same_name,
            "SelectNameUnique": select_name_unique,
            "SelectNameCommon": select_name_common,
            "SelectStemMatchCase": invoke_regex_selector(True),
            "SelectStemMatch": invoke_regex_selector(False),
            "SelectStemStartsWith": select_stem_startswith,
            "SelectStemEndsWith": select_stem_endswith,
            "SelectStemContains": select_stem_contains,
            "SelectByExtension": select_byext,
        }
    )


def configure_ListWindow(window: ckit.TextWindow) -> None:

    def refresh() -> None:
        window.scroll_info.makeVisible(
            window.select, window.itemsHeight(), window.scroll_margin
        )
        window.paint()

    def to_top(_) -> None:
        window.select = 0
        refresh()

    def to_bottom(_) -> None:
        window.select = len(window.items) - 1
        refresh()

    def smart_cursorUp(_) -> None:
        if window.select == 0:
            window.select = len(window.items) - 1
        else:
            window.select -= 1
        refresh()

    def smart_cursorDown(_) -> None:
        if window.select == len(window.items) - 1:
            window.select = 0
        else:
            window.select += 1
        refresh()

    window.keymap["A"] = to_top
    window.keymap["Home"] = to_top
    window.keymap["E"] = to_bottom
    window.keymap["End"] = to_bottom
    window.keymap["J"] = smart_cursorDown
    window.keymap["Down"] = smart_cursorDown
    window.keymap["K"] = smart_cursorUp
    window.keymap["Up"] = smart_cursorUp
    window.keymap["C-J"] = window.command_CursorDownMark
    window.keymap["C-K"] = window.command_CursorUpMark
    for mod in ["", "S-"]:
        for key in ["L", "Space", "Right"]:
            window.keymap[mod + key] = window.command_Enter


def configure_TextViewer(window: ckit.TextWindow) -> None:
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
        window.scroll_info.pos = window._numLines() - 1
        window.paint()

    window.keymap["E"] = to_bottom
    window.keymap["End"] = to_bottom

    def edit_by(_):
        te = TEXT_EDITORS
        names = te.names
        if len(names) < 1:
            return

        delay()
        result, _ = invoke_listwindow(window, "open with:", names)

        if result < 0:
            return

        editor_path = te.get_path(names[result])
        pyauto.shellExecute(None, editor_path, window.item.getFullpath(), "")
        window.command_Close(None)

    window.keymap["C-E"] = edit_by

    def open_original(_) -> None:
        pane = window.main_window.activePane()
        visible = isinstance(pane.file_list.getLister(), lister_Default)
        path = Path(window.item.getFullpath())
        window.command_Close(None)
        pane.history.append(str(path.parent), path.name, visible, True)
        pyauto.shellExecute(None, str(path), "", "")

    window.keymap["C-Enter"] = open_original
    window.keymap["C-L"] = open_original

    def get_encoding() -> str:
        enc = window.encoding.encoding
        if enc:
            if enc == "utf-8" and window.encoding.bom:
                enc += "-sig"
            return enc
        return ""

    def get_fullpath() -> str:
        return window.item.getFullpath()

    def get_content(path: str = "") -> str:
        p = get_fullpath() if len(path) < 1 else path
        enc = get_encoding()
        if enc:
            return Path(p).read_text(enc)
        return ""

    def copy_content(_) -> None:
        c = get_content()
        n = Path(get_fullpath()).name
        if len(c) < 1:
            msg = "nothing was copied: '{}' is not text file.".format(n)
        else:
            ckit.setClipboardText(c)
            msg = "copied content of '{}'.".format(n)
        print("\n{}\n".format(msg))
        delay(200)
        window.command_Close(None)

    window.keymap["C-C"] = copy_content

    def copy_line_at_top(_) -> None:
        c = get_content()
        if len(c) < 1:
            return
        line = c.splitlines()[window.scroll_info.pos]
        ckit.setClipboardText(line)

    window.keymap["C-T"] = copy_line_at_top

    def copy_displayed_lines(_) -> None:
        c = get_content()
        if len(c) < 1:
            return
        lines = c.splitlines()
        top = window.scroll_info.pos
        bottom = min(top + window.height() - 1, top + window._numLines() - 1)
        s = "\n".join(lines[top:bottom])
        ckit.setClipboardText(s)

    window.keymap["C-S-C"] = copy_displayed_lines

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
        result, _ = invoke_listwindow(window, "encoding", names)
        if result < 0:
            return

        enc = encodes[names[result]]
        auto_flag = enc is not None and len(enc) < 1
        window.load(auto=auto_flag, encoding=ckit.TextEncoding(enc))

        window.scroll_info.makeVisible(0, window.height() - 1)

    window.keymap["C-Comma"] = reload_with_encoding
    window.keymap["Z"] = reload_with_encoding


def configure_ImageViewer(window: ckit.TextWindow) -> None:
    window.keymap["F11"] = window.command_ToggleMaximize
    window.keymap["H"] = window.command_CursorUp
    window.keymap["J"] = window.command_CursorDown
    window.keymap["K"] = window.command_CursorUp
    window.keymap["L"] = window.command_CursorDown
    window.keymap["S-Semicolon"] = window.command_ZoomIn
    window.keymap["Z"] = window.command_ZoomIn
    window.keymap["Minus"] = window.command_ZoomOut
    window.keymap["S-Z"] = window.command_ZoomOut
    window.keymap["S-Minus"] = window.command_ZoomPolicyOriginal
    window.keymap["Left"] = window.command_CursorUp
    window.keymap["Right"] = window.command_CursorDown
    window.keymap["Down"] = window.command_CursorDown
    window.keymap["Up"] = window.command_CursorUp
    window.keymap["S-Left"] = window.command_ScrollLeft
    window.keymap["S-Right"] = window.command_ScrollRight
    window.keymap["S-Down"] = window.command_ScrollDown
    window.keymap["S-Up"] = window.command_ScrollUp
    window.keymap["S-H"] = window.command_ScrollLeft
    window.keymap["S-L"] = window.command_ScrollRight
    window.keymap["S-J"] = window.command_ScrollDown
    window.keymap["S-K"] = window.command_ScrollUp
    window.keymap["Q"] = window.command_Close

    def to_top(_) -> None:
        if 0 < window.job_queue.numItems():
            return
        if window.cursor == 0:
            return
        window.cursor = 0
        if window.cursor_handler:
            window.cursor_handler(window.items[window.cursor])
        window.decode()

    window.keymap["A"] = to_top
    window.keymap["Home"] = to_top

    def to_last(_) -> None:
        if 0 < window.job_queue.numItems():
            return
        last = len(window.items) - 1
        if window.cursor == last:
            return
        window.cursor = last
        if window.cursor_handler:
            window.cursor_handler(window.items[window.cursor])
        window.decode()

    window.keymap["E"] = to_last
    window.keymap["End"] = to_last

    def toggle_zoom(_) -> None:
        if window.zoom_policy == "original":
            window.command_ZoomPolicyFit(None)
        else:
            window.command_ZoomPolicyOriginal(None)

    window.keymap["O"] = toggle_zoom
    window.keymap["F"] = toggle_zoom

    def open_original(_) -> None:
        item = window.items[window.cursor]
        path = item.getFullpath()
        window.command_Close(None)
        pyauto.shellExecute(None, path, "", "")

    window.keymap["C-Enter"] = open_original
    window.keymap["C-L"] = open_original

    def copy_image_to_clioboard(_) -> None:
        def _copy(_) -> None:
            item = window.items[window.cursor]
            path = item.getFullpath()
            cmd = [
                "PowerShell",
                "-Command",
                "Add-Type",
                "-AssemblyName",
                "System.Windows.Forms;[Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile('{}'));".format(
                    path
                ),
            ]
            subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW)

        def _finished(_) -> None:
            window.setTitle(
                "{} - [ {} ] copied!".format(
                    cfiler_resource.cfiler_appname, window.items[window.cursor].name
                )
            )

        job = ckit.JobItem(_copy, _finished)
        window.job_queue.enqueue(job)

    window.keymap["C-C"] = copy_image_to_clioboard
