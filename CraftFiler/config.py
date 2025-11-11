import configparser
import datetime
import fnmatch
import hashlib
import inspect
import os
import re
import shutil
import subprocess
import time
import unicodedata
import urllib.parse
import urllib.request
import webbrowser
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
from winreg import HKEY_CURRENT_USER, HKEY_CLASSES_ROOT, OpenKey, QueryValueEx

from PIL import ImageGrab
from PIL import Image as PILImage
from PIL.ExifTags import TAGS

from pathlib import Path
from typing import List, Tuple, Callable, Union, NamedTuple, Iterator, Dict, Protocol
import tempfile

import ckit  # type: ignore
import pyauto  # type: ignore

from cfiler import *  # type: ignore


# https://github.com/crftwr/cfiler/blob/master/cfiler_mainwindow.py
import cfiler_mainwindow  # type: ignore
from cfiler_mainwindow import MainWindow  # type: ignore

# https://github.com/crftwr/cfiler/blob/master/cfiler_filelist.py
from cfiler_filelist import (  # type: ignore
    FileList,
    item_Default,
    lister_Default,
    item_Empty,
    filter_Default,
)

# https://github.com/crftwr/cfiler/blob/master/cfiler_listwindow.py
from cfiler_listwindow import ListWindow  # type: ignore

# https://github.com/crftwr/cfiler/blob/master/cfiler_textviewer.py
from cfiler_textviewer import TextViewer  # type: ignore

# https://github.com/crftwr/cfiler/blob/master/cfiler_renamewindow.py
from cfiler_resultwindow import popResultWindow  # type: ignore

# https://github.com/crftwr/cfiler/blob/master/cfiler_misc.py
from cfiler_misc import getFileSizeString  # type: ignore

# https://github.com/crftwr/cfiler/blob/master/cfiler_resource.py
import cfiler_resource  # type: ignore

import cfiler_msgbox  # type: ignore
import cfiler_debug  # type: ignore


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


def stringify(x: Union[str, None], trim: bool = True) -> str:
    if x:
        if trim:
            return x.strip()
        return x
    return ""


def is_file_locked(path: Union[Path, str]) -> bool:
    try:
        with open(path, "a"):
            return False
    except OSError:
        return True


def smart_check_path(
    path: Union[str, Path], timeout_sec: Union[int, float, None] = None
) -> bool:
    """CASE-INSENSITIVE path check with timeout"""
    p = path if isinstance(path, Path) else Path(path)
    try:
        future = ThreadPoolExecutor(max_workers=1).submit(p.exists)
        return future.result(timeout_sec)
    except:
        return False


DESKTOP_PATH = os.path.expandvars(r"${USERPROFILE}\Desktop")


def check_fzf() -> bool:
    return shutil.which("fzf.exe") is not None


def open_vscode(*args: str) -> bool:
    try:
        if code_path := shutil.which("code"):
            cmd = [code_path] + list(args)
            subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
            return True
        return False
    except Exception as e:
        print(e)
        return False


def shell_exec(path: str, *args) -> None:
    if not isinstance(path, str):
        path = str(path)
    if path.startswith("http"):
        webbrowser.open(path)
        return
    path = os.path.expandvars(path)
    try:
        cmd = ["start", "", path] + list(args)
        subprocess.run(cmd, shell=True)
    except Exception as e:
        print(e)


CallbackFunc = Callable[[], None]


class PaneHistoryProtocol(Protocol):
    def append(self, parent: str, name: str, visible: bool, mark: bool) -> None: ...

    items: list


class PaneEntityProtocol(Protocol):
    cursor: int
    history: PaneHistoryProtocol
    file_list: FileList
    scroll_info: ckit.ScrollInfo


class ItemDefaultProtocol(Protocol):
    def isdir(self) -> bool: ...
    def getName(self) -> str: ...
    def getFullpath(self) -> str: ...
    def bookmark(self) -> list: ...
    def time(self) -> tuple: ...
    def selected(self) -> bool: ...
    def size(self) -> int: ...


def configure(window: MainWindow) -> None:

    if ckit.CronTable.defaultCronTable():
        ckit.CronTable.defaultCronTable().cancel()
        ckit.CronTable.defaultCronTable().clear()
    else:
        ckit.CronTable.createDefaultCronTable()

    class PanePartsMinWidth:
        date = 11
        time = 9
        filesize = 6

    class ItemTimestamp:
        def __init__(self, item) -> None:
            self._time = item.time()
            self._now = time.localtime()

        def _datestr(self) -> str:
            t = self._time
            if t[0] == self._now[0]:
                if t[1] == self._now[1] and t[2] == self._now[2]:
                    return ""
                return "{:02}-{:02}".format(t[1], t[2])
            return "{}-{:02}-{:02}".format(t[0], t[1], t[2])

        def _timestr(self) -> str:
            t = self._time
            return "{:02}:{:02}:{:02}".format(t[3], t[4], t[5])

        def tostr(self) -> str:
            return self._datestr().rjust(
                PanePartsMinWidth.date
            ) + self._timestr().rjust(PanePartsMinWidth.time)

    def itemformat_NativeName_Ext_Size_YYYYMMDDorHHMMSS(
        window: MainWindow, item: ItemDefaultProtocol, width: int, _
    ) -> str:
        if item.isdir():
            str_size = "\ud83d\udcc1"
        else:
            str_size = getFileSizeString(item.size())

        str_size_time = (
            str_size.rjust(PanePartsMinWidth.filesize) + ItemTimestamp(item).tostr()
        )

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

    def set_custom_theme() -> None:
        custom_theme = {
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

        name = "black"
        ckit.ckit_theme.theme_name = name
        window.ini.set("THEME", "name", name)

        for k, v in custom_theme.items():
            rgb = tuple(int(v[i : i + 2], 16) for i in (1, 3, 5))
            ckit.ckit_theme.ini.set("COLOR", k, str(rgb))

        window.destroyThemePlane()
        window.createThemePlane()
        window.updateColor()
        window.updateWallpaper()

    set_custom_theme()

    class Kiritori:
        sep = "-"

        @staticmethod
        def get_width() -> int:
            return window.width()

        @classmethod
        def _draw_header(cls) -> None:
            print("\n{}".format(cls.sep * cls.get_width()))

        @classmethod
        def _draw_footer(cls) -> None:
            ts = datetime.datetime.today().strftime(
                " %Y-%m-%d %H:%M:%S.%f {}".format(cls.sep * 2)
            )
            print("{}\n".format(ts.rjust(cls.get_width(), cls.sep)))

        @classmethod
        def log(cls, s) -> None:
            cls._draw_header()
            print(s)
            cls._draw_footer()

        @classmethod
        def wrap(cls, func: CallbackFunc) -> None:
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

    class Keybinder:

        @staticmethod
        def wrap(
            func: Callable[..., None],
        ) -> Callable[[ckit.ckit_command.CommandInfo], None]:
            if len(inspect.signature(func).parameters) < 1:

                def _callback(_) -> None:
                    func()

                return _callback

            return func

        @classmethod
        def bind(
            cls,
            func: Callable[..., None],
            *keys: str,
        ) -> None:
            for key in keys:
                window.keymap[key] = cls.wrap(func)

    def apply_cfiler_command(mapping: dict) -> None:
        for key, func in mapping.items():
            window.keymap[key] = func

    apply_cfiler_command(
        {
            "C": window.command_Copy,
            "M": window.command_Move,
            "S-Enter": window.command_View,
            "C-S-Q": window.command_CancelTask,
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
            "C-N": window.command_DuplicateCfiler,
            "OpenBracket": window.command_MoveSeparatorLeft,
            "CloseBracket": window.command_MoveSeparatorRight,
            "Yen": window.command_MoveSeparatorCenter,
            "A-S": window.command_SetSorter,
            "S-J": window.command_LogDown,
            "S-K": window.command_LogUp,
            "S-OpenBracket": window.command_MoveSeparatorUp,
            "S-CloseBracket": window.command_MoveSeparatorDown,
            "C-S-R": window.command_BatchRename,
        }
    )

    class CPane:
        min_width = 20

        def __init__(self, active: bool = True) -> None:
            if active:
                self._pane = window.activePane()
                self._items = window.activeItems()
                self._other = window.inactivePane()
            else:
                self._pane = window.inactivePane()
                self._items = window.inactiveItems()
                self._other = window.activePane()

        @property
        def entity(self) -> PaneEntityProtocol:
            return self._pane

        def repaint(self, option: PaintOption = PaintOption.All) -> None:
            window.paint(option.value)

        def refresh(self) -> None:
            window.subThreadCall(self.fileList.refresh, (False, True))
            self.fileList.applyItems()

        def setSorter(
            self, sorter: Callable[[List[ItemDefaultProtocol]], None]
        ) -> None:
            window.subThreadCall(self.fileList.setSorter, (sorter,))
            self.refresh()

        @property
        def items(self) -> List[ItemDefaultProtocol]:
            if self.isBlank:
                return []
            return self._items

        @property
        def dirs(self) -> List[ItemDefaultProtocol]:
            items = []
            if self.isBlank:
                return items
            for i in range(self.count):
                item = self.byIndex(i)
                if item.isdir():
                    items.append(item)
            return items

        @property
        def files(self) -> List[ItemDefaultProtocol]:
            items = []
            if self.isBlank:
                return items
            for i in range(self.count):
                item = self.byIndex(i)
                if not item.isdir():
                    items.append(item)
            return items

        @property
        def stems(self) -> List[str]:
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
            return self.entity.cursor

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

        @property
        def width(self) -> int:
            left_width = window.left_window_width
            left_focused = window.focus == MainWindow.FOCUS_LEFT
            if left_focused and self.entity == window.activePane():
                return left_width
            if not left_focused and self.entity == window.inactivePane():
                return left_width
            return window.width() - left_width

        def adjustWidth(self) -> None:
            if window.width() - self.width < self.min_width:
                window.command_MoveSeparatorCenter(None)

        def focusOther(self, adjust: bool = True) -> None:
            if adjust:
                self.adjustWidth()
            window.command_FocusOther(None)

        @property
        def fileList(self) -> FileList:
            return self.entity.file_list

        @property
        def lister(self) -> lister_Default:
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
            return self.entity.scroll_info

        @property
        def currentPath(self) -> str:
            return self.fileList.getLocation()

        @property
        def count(self) -> int:
            return self.fileList.numItems()

        def byIndex(self, i: int) -> ItemDefaultProtocol:
            return self.fileList.getItem(i)

        @property
        def isBlank(self) -> bool:
            return isinstance(self.byIndex(0), item_Empty)

        @property
        def names(self) -> List[str]:
            names = []
            if self.isBlank:
                return names
            for i in range(self.count):
                item = self.byIndex(i)
                names.append(item.getName())
            return names

        @property
        def paths(self) -> List[str]:
            return [os.path.join(self.currentPath, name) for name in self.names]

        @property
        def extensions(self) -> List[str]:
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
        def selectedItems(self) -> List[ItemDefaultProtocol]:
            items = []
            if self.isBlank:
                return items
            for i in range(self.count):
                item = self.byIndex(i)
                if item.selected():
                    items.append(item)
            return items

        @property
        def selectedOrAllItems(self) -> List[ItemDefaultProtocol]:
            if self.hasSelection:
                return self.selectedItems
            return self.items

        @property
        def selectedItemPaths(self) -> List[str]:
            return [item.getFullpath() for item in self.selectedItems]

        @property
        def selectedItemNames(self) -> List[str]:
            return [item.getName() for item in self.selectedItems]

        @property
        def focusedItem(self) -> ItemDefaultProtocol:
            if self.isBlank:
                raise ValueError("No item to focus.")
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
            self.repaint(PaintOption.Upper)

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
            self.scrollInfo.makeVisible(i, window.fileListItemPaneHeight(), 1)
            self.repaint(PaintOption.FocusedItems)

        def scrollToCursor(self) -> None:
            self.scrollTo(self.cursor)

        def openChild(self, name: str) -> None:
            self.openPath(os.path.join(self.currentPath, name))

        def openPath(self, path: str, focus_name: Union[None, str] = None) -> None:
            if self.currentPath == path:
                if focus_name is not None:
                    self.focusByName(focus_name)
                return
            target = Path(path)
            if not smart_check_path(target):
                Kiritori.log("invalid path: '{}'".format(path))
                return
            if target.is_file():
                path = str(target.parent)
                focus_name = target.name
            else:
                if focus_name is None:

                    def _last_focused_name(hist_item: list) -> Union[str, None]:
                        dir_path = hist_item[0]
                        if dir_path.startswith(path):
                            if dir_path == path:
                                return hist_item[1]
                            return dir_path[len(path) + 1 :].split(os.sep)[0]
                        return None

                    for hist_item in (
                        self.entity.history.items + self._other.history.items
                    ):
                        focus_name = _last_focused_name(hist_item)
                        if focus_name is not None:
                            break

            lister = lister_Default(window, path)
            window.jumpLister(self.entity, lister, focus_name)

        def touch(self, name: str) -> None:
            if not hasattr(self.lister, "touch"):
                Kiritori.log("cannot make file here.")
                return
            dp = Path(self.currentPath, name)
            if smart_check_path(dp) and dp.is_file():
                Kiritori.log("file '{}' already exists.".format(name))
                return
            window.subThreadCall(self.lister.touch, (name,))
            self.refresh()
            self.focus(window.cursorFromName(self.fileList, name))

        def mkdir(self, name: str, focus: bool = True) -> None:
            if not hasattr(self.lister, "mkdir"):
                Kiritori.log("cannot make directory here.")
                return
            dp = Path(self.currentPath, name)
            if smart_check_path(dp) and dp.is_dir():
                Kiritori.log("directory '{}' already exists.".format(name))
                self.focusByName(name)
                return
            window.subThreadCall(self.lister.mkdir, (name, None))
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

        def traverse(
            self, only_file: bool, *ignore_dirnames: str
        ) -> Iterator[ItemDefaultProtocol]:

            class FileListEntry:
                def __init__(self, root: str, path: str) -> None:
                    self.root = root
                    self.dirname = path[len(root) :].lstrip(os.sep)

                def __call__(self, name) -> Union[ItemDefaultProtocol, None]:
                    try:
                        item: ItemDefaultProtocol = item_Default(
                            self.root, ckit.joinPath(self.dirname, name)
                        )
                        return item
                    except Exception:
                        cfiler_debug.printErrorInfo()
                        return None

            ignore_list = list(ignore_dirnames) + ["node_modules"]
            for dirpath, subdirs, subfiles in os.walk(self.currentPath):
                for dn in subdirs:
                    if dn.startswith(".") or dn in ignore_list:
                        subdirs.remove(dn)
                for fn in subfiles:
                    if fn.startswith("~$_"):
                        subfiles.remove(fn)
                ent = FileListEntry(self.currentPath, dirpath)
                if not only_file:
                    for d in filter(
                        None,
                        map(ent, subdirs),
                    ):
                        yield d
                for f in filter(None, map(ent, subfiles)):
                    yield f

    class LeftPane(CPane):
        def __init__(self) -> None:
            super().__init__(window.focus == MainWindow.FOCUS_LEFT)

        def activate(self) -> None:
            if window.focus == MainWindow.FOCUS_RIGHT:
                window.focus = MainWindow.FOCUS_LEFT
            self.repaint(PaintOption.LeftOrRight)

    class RightPane(CPane):
        def __init__(self) -> None:
            super().__init__(window.focus == MainWindow.FOCUS_RIGHT)

        def activate(self) -> None:
            if window.focus == MainWindow.FOCUS_LEFT:
                window.focus = MainWindow.FOCUS_RIGHT
            self.repaint(PaintOption.LeftOrRight)

    def smart_cursorUp() -> None:
        pane = CPane()
        if pane.isBlank or pane.count == 1:
            return
        if pane.cursor == 0:
            pane.entity.cursor = pane.count - 1
        else:
            pane.entity.cursor -= 1
        pane.scrollToCursor()

    Keybinder().bind(smart_cursorUp, "K", "Up")

    def smart_cursorDown() -> None:
        pane = CPane()
        if pane.isBlank or pane.count == 1:
            return
        if pane.cursor == pane.count - 1:
            pane.entity.cursor = 0
        else:
            pane.entity.cursor += 1
        pane.scrollToCursor()

    Keybinder().bind(smart_cursorDown, "J", "Down")

    def focus_latest_item() -> None:
        pane = CPane()
        if pane.isBlank:
            return
        latest = None
        for item in pane.selectedOrAllItems:
            if latest is None:
                latest = item
                continue
            if latest.time() <= item.time():
                latest = item

        if latest:
            pane.focusByName(latest.getName())

    Keybinder().bind(focus_latest_item, "A-N")

    def copy_dir_tree() -> None:
        pane = CPane()
        root = pane.currentPath
        window.setProgressValue(None)

        def _traverse(job_item: ckit.JobItem) -> None:
            job_item.paths = []
            for item in pane.traverse(False):
                if job_item.isCanceled():
                    return
                rel = item.getFullpath()[len(root) :].lstrip(os.sep)
                job_item.paths.append(rel)

        def _finished(job_item: ckit.JobItem) -> None:
            window.clearProgress()
            if job_item.isCanceled():
                Kiritori.log("Canceled.")
            else:
                lines = "\n".join(sorted(job_item.paths))
                ckit.setClipboardText(lines)
                Kiritori.log("Copied tree: {}".format(root))

        job = ckit.JobItem(_traverse, _finished)
        window.taskEnqueue(job, create_new_queue=False)

    Keybinder().bind(copy_dir_tree, "C-T")

    def show_path_tree(path: str) -> None:
        if len(path) < 1:
            return

        def _show() -> None:
            p = Path(path)
            stack = [p.name]
            for parent in p.parents:
                if n := parent.name:
                    stack.append(n)
                if smart_check_path(os.path.join(parent, ".root")):
                    break
            stack.reverse()
            for i, s in enumerate(stack):
                b = "" if i == 0 else " \u2514"
                print(b, s)

        Kiritori.wrap(_show)

    Keybinder().bind(lambda: show_path_tree(CPane().focusedItemPath), "Y")

    def open_latest_under_tree() -> None:
        pane = CPane()
        if pane.isBlank:
            return

        print("Searching for newest file under '{}' ...".format(pane.currentPath))

        def _scan(job_item: ckit.JobItem) -> None:
            job_item.latest = None
            for item in pane.traverse(True, "_obsolete"):
                if job_item.latest is None:
                    job_item.latest = item
                    continue
                if job_item.latest.time() <= item.time():
                    job_item.latest = item

        def _open(job_item: ckit.JobItem) -> None:
            if job_item.latest:
                p = job_item.latest.getFullpath()
                pane.openPath(p)
                show_path_tree(p)

        job = ckit.JobItem(_scan, _open)
        window.taskEnqueue(job, create_new_queue=False)

    Keybinder().bind(open_latest_under_tree, "C-S-A-N")

    def focus_by_timestamp() -> None:
        pane = CPane()
        if pane.isBlank:
            return
        focused = pane.focusedItem
        older = []
        for item in pane.selectedOrAllItems:
            if item.time() < focused.time():
                older.append(item)

        if 0 < len(older):
            last = sorted(older, key=lambda x: x.time())[-1]
            pane.focusByName(last.getName())

    Keybinder().bind(focus_by_timestamp, "A-Back", "A-B")

    def adjust_pane_wifth() -> None:
        pane = CPane()
        stems = [Path(f.getFullpath()).stem for f in pane.files]
        if len(stems) < 1:
            return
        longest = sorted(stems, key=len, reverse=True)[0]
        stem_min_width = window.getStringWidth(longest)
        ext_min_width = len(" .xxxx")
        filesize_min_width = len(" 999.9M")
        timestamp_min_width = len(" yyyy-MM-dd hh:mm:ss")
        window.left_window_width = (
            stem_min_width + ext_min_width + filesize_min_width + timestamp_min_width
        )
        window.updateThemePosSize()
        pane.repaint(PaintOption.Upper)

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
        CPane().repaint(PaintOption.Upper)

    Keybinder().bind(toggle_pane_width, "C-S")

    Keybinder().bind(lambda: CPane().focusOther(), "C-L")

    def is_extractable(ext: str) -> bool:
        for archiver in window.archiver_list:
            for pattern in archiver[0].split():
                if ext == pattern[1:]:
                    return True
        return False

    def peek_archive(path: str) -> None:
        p = Path(path)
        archiver = window.getArchiver(p.name)
        if not archiver:
            return

        def _peek(job_item: ckit.JobItem) -> None:
            job_item.name = p.name
            job_item.tree = []

            arc = archiver.openArchive(window.getHWND(), path, 0)
            try:
                for info in arc.iterItems("*"):
                    job_item.tree.append(info[0])
            finally:
                arc.close()

        def _finished(job_item: ckit.JobItem) -> None:
            def __show() -> None:
                print(job_item.name)
                for line in job_item.tree:
                    print("  ", line)

            Kiritori.wrap(__show)

        job = ckit.JobItem(_peek, _finished)
        window.taskEnqueue(job, create_new_queue=False)

    def invoke_listwindow(
        prompt: str, items: list, cursor_pos: int = 0
    ) -> Tuple[int, int]:
        pos = window.centerOfFocusedPaneInPixel()
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
            initial_select=cursor_pos,
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

    def hook_enter() -> bool:

        pane = CPane()
        if pane.isBlank:
            pane.focusOther()
            return True

        focus_path = pane.focusedItemPath
        p = Path(focus_path)
        if p.is_dir():
            pane.openPath(focus_path)
            return True

        if pane.focusedItem.size() == 0:
            window.command_Execute(None)
            return True

        ext = p.suffix

        if ext in window.image_file_ext_list:
            pane.appendHistory(focus_path, True)
            return False

        if ext in window.music_file_ext_list:
            window.command_Execute(None)
            return True

        if is_extractable(ext):
            peek_archive(focus_path)
            return True

        if ext.lower() in [
            ".docx",
            ".xlsx",
        ]:
            menu = ["Open"]
            if ext == ".docx":
                menu.append("(peek text)")
            else:
                menu.append("(peek text of sheet1)")
            result, _ = invoke_listwindow("OpenXML file:", menu)
            if result != -1:
                if result == 0:
                    window.command_Execute(None)
                else:
                    preview_openxml_content(focus_path)
            return True

        if ext[1:].lower() in [
            "webp",
            "m4a",
            "mp4",
            "pdf",
            "xls",
            "doc",
            "pptx",
            "ppt",
        ]:
            window.command_Execute(None)
            return True

        return False

    window.enter_hook = hook_enter

    Keybinder().bind(window.command_Enter, "L", "Right")

    def toggle_hidden() -> None:
        window.showHiddenFile(not window.isHiddenFileVisible())

    Keybinder().bind(toggle_hidden, "C-S-H")

    def get_default_browser() -> str:
        register_path = r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice"
        prog_id = None
        with OpenKey(HKEY_CURRENT_USER, register_path) as key:
            prog_id = str(QueryValueEx(key, "ProgId")[0])

        if not prog_id:
            return ""

        commandline = None
        register_path = r"{}\shell\open\command".format(prog_id)
        with OpenKey(HKEY_CLASSES_ROOT, register_path) as key:
            commandline = str(QueryValueEx(key, "")[0])

        if not commandline:
            return ""

        ext = ".exe"
        return commandline[: commandline.find(ext) + len(ext)].strip('"')

    def open_with() -> None:
        pane = CPane()
        if pane.isBlank:
            return

        if any([item.isdir() for item in pane.selectedItems]):
            return

        paths = pane.selectedItemPaths
        if len(paths) < 1 and not pane.focusedItem.isdir():
            paths.append(pane.focusedItemPath)

        app_table = {}
        if len(set([Path(p).suffix for p in paths])) != 1:
            app_table["(associated app)"] = shell_exec

        if any([path.endswith(".pdf") for path in paths]):
            app_table["sumatra"] = r"C:\Program Files\SumatraPDF\SumatraPDF.exe"
            app_table["adobe"] = (
                r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe"
            )
            app_table["xedit"] = (
                r"C:\Program Files\Tracker Software\PDF Editor\PDFXEdit.exe"
            )
            browser_path = get_default_browser()
            if browser_path:
                app_table["browser"] = browser_path

        app_table["notepad"] = r"C:\Windows\System32\notepad.exe"
        app_table["mery"] = os.path.expandvars(
            r"${LOCALAPPDATA}\Programs\Mery\Mery.exe"
        )
        app_table["vscode"] = lambda x: open_vscode(x)

        names = list(app_table.keys())

        result, _ = invoke_listwindow("open with:", names)
        if result < 0:
            return

        exe = app_table[names[result]]
        for path in paths:
            if isinstance(exe, Callable):
                exe(path)
            else:
                shell_exec(exe, path)

    Keybinder().bind(open_with, "C-O")

    def quick_move() -> None:
        pane = CPane()
        if not pane.hasSelection:
            window.command_Select(None)
        pane.adjustWidth()
        window.command_Move(None)

    Keybinder().bind(quick_move, "M")

    def quick_copy() -> None:
        pane = CPane()
        if not pane.hasSelection:
            window.command_Select(None)
        pane.adjustWidth()
        window.command_Copy(None)

    Keybinder().bind(quick_copy, "C")

    def swap_pane() -> None:
        active = CPane(True)
        active_selects = active.selectedItemNames
        active_path = active.currentPath
        active_focus_name = None if active.isBlank else active.focusedItem.getName()
        active_sorter = active.fileList.getSorter()

        other = CPane(False)
        ogther_selects = other.selectedItemNames
        other_path = other.currentPath
        other_sorter = other.fileList.getSorter()

        other_focus_name = None if other.isBlank else other.focusedItem.getName()

        active.openPath(other_path, other_focus_name)
        active.selectByNames(ogther_selects)
        active.setSorter(other_sorter)

        other.openPath(active_path, active_focus_name)
        other.selectByNames(active_selects)
        other.setSorter(active_sorter)

        LeftPane().activate()

    Keybinder().bind(swap_pane, "S")

    class BookmarkAlias:
        ini_section = "BOOKMARK_ALIAS"

        def __init__(self) -> None:
            try:
                window.ini.add_section(self.ini_section)
            except configparser.DuplicateSectionError:
                pass

        def register(self, name: str, path: str) -> None:
            window.ini.set(self.ini_section, name, path)

        def clear_by_path(self, path: str) -> None:
            for opt in window.ini.items(self.ini_section):
                if opt[1] == path:
                    window.ini.remove_option(self.ini_section, opt[0])

        @staticmethod
        def to_last_elem(path: str) -> str:
            path = path.rstrip(os.sep)
            p = Path(path)
            if 0 < len(p.name):
                return p.name
            return path.split(os.sep)[-1]

        def alias_of(self, path: str) -> str:
            for opt in window.ini.items(self.ini_section):
                if opt[1] == path:
                    return opt[0]
            return ""

        def to_dict(self) -> Dict[str, str]:
            d = {}
            for path in window.bookmark.getItems():
                leaf = self.to_last_elem(path)
                if 0 < len(a := self.alias_of(path)):
                    leaf = "{}[{}]".format(a, self.to_last_elem(path))
                d[leaf] = path
            return d

    class FuzzyBookmark:

        def __init__(self) -> None:
            self._table = BookmarkAlias().to_dict()

        def fzf(self) -> str:
            table = self._table
            src = "\n".join(sorted(table.keys(), reverse=True))
            try:
                cmd = ["fzf.exe", "--margin=1", "--no-color", "--input-border=sharp"]
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

        pane = CPane()

        def _get_path(job_item: ckit.JobItem) -> None:
            fb = FuzzyBookmark()
            job_item.path = fb.fzf()

        def _open(job_item: ckit.JobItem) -> None:
            path = job_item.path
            if 0 < len(path):
                pane.openPath(path)

        job = ckit.JobItem(_get_path, _open)
        window.taskEnqueue(job, create_new_queue=False)

    Keybinder().bind(fuzzy_bookmark, "B")

    def cleanup_alias_for_unbookmarked() -> None:
        cleared = []
        section_name = BookmarkAlias.ini_section
        bookmarks = window.bookmark.getItems()
        for opt in window.ini.items(section_name):
            alias, path = opt[:2]
            if path not in bookmarks:
                window.ini.remove_option(section_name, alias)
                cleared.append((alias, path))

        def _display() -> None:
            if 0 < len(cleared):
                if len(cleared) == 1:
                    print("Removed alias for unbookmarked:")
                else:
                    print("Removed aliases for unbookmarked:")
                for c in cleared:
                    print("- '{}' for '{}'".format(*c))

        Kiritori().wrap(_display)

    def set_bookmark_alias() -> None:
        pane = CPane()
        target = pane.currentPath
        if pane.hasSelection:
            if 1 < len(pane.selectedItems):
                Kiritori.log(
                    "Canceled. Select just 1 item (or nothing to bookmark current location)."
                )
                return
            else:
                target = pane.selectedItemPaths[0]

        ba = BookmarkAlias()

        alias = stringify(window.commandLine("Bookmark alias"))
        if len(alias) < 1:
            ba.clear_by_path(target)
            Kiritori.log("Removed all alias for '{}'".format(target))
            return

        ba.register(alias, target)

        if target not in window.bookmark.getItems():
            window.bookmark.append(target)
            if target != pane.currentPath:
                pane.refresh()
        Kiritori.log("Registered '{}' as alias for '{}'".format(alias, target))

    def read_openxml(path: str) -> str:
        go_tool = {
            ".docx": "docxr.exe",
            ".xlsx": "xlsxr.exe",
        }.get(Path(path).suffix, None)
        if go_tool is None:
            return ""

        exe_path = shutil.which(go_tool)
        if not exe_path:
            Kiritori.log("'{}' not found...".format(go_tool))
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

    TEMP_FILE_PREFIX = "cfiler_preview_openxml_"

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
                tf = tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    delete=False,
                    suffix=".txt",
                    prefix=TEMP_FILE_PREFIX,
                )
                tf.write(content)
                tf.close()
                job_item.temp_path = tf.name
            except Exception as e:
                Kiritori.log(e)

        def _view_tempfile(job_item: ckit.JobItem) -> None:
            if job_item.temp_path:
                d, n = os.path.split(job_item.temp_path)
                item = item_Default(d, n)
                window._viewCommon(d, item)

        job = ckit.JobItem(_write_to_tempfile, _view_tempfile)
        window.taskEnqueue(job, create_new_queue=False)

    def remove_tempfiles() -> None:
        temp_dir = tempfile.gettempdir()
        paths = []
        for file in os.listdir(temp_dir):
            if file.startswith(TEMP_FILE_PREFIX) and file.endswith(".txt"):
                try:
                    os.remove(os.path.join(temp_dir, file))
                    paths.append(file)
                except Exception as e:
                    Kiritori.log("Failed to remove temp file : {}".format(e))

        if len(paths) < 1:
            return

        def _log() -> None:
            count = len(paths)
            msg = "Removed {} temp file".format(count)
            if 1 < count:
                msg += "s"
            print(msg)
            for p in paths:
                print("-", p)

        Kiritori.wrap(_log)

    def register_tempfile_cleaner_cron() -> None:
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
                    except Exception as e:
                        Kiritori.log(
                            "Failed to remove temp file :{}\n{}".format(file, e)
                        )

            if 0 < count:
                msg = "Removed {} tempfile".format(count)
                if 1 < count:
                    msg += "s"
                msg += " for preview."
                window.setStatusMessage(msg, 8000)

        ci = ckit.CronItem(_crean, 30.0)
        ckit.CronTable.defaultCronTable().add(ci)

    register_tempfile_cleaner_cron()

    def docx_to_txt() -> None:
        def _convert(path: str) -> None:
            if not path.endswith(".docx"):
                return

            def __read(job_item: ckit.JobItem) -> None:
                job_item.result = read_openxml(path)

            def __write(job_item: ckit.JobItem) -> None:
                new_path = Path(path).with_suffix(".txt")
                if smart_check_path(new_path):
                    Kiritori.log("Path duplicates: '{}'".format(new_path))
                else:
                    new_path.write_text(job_item.result, encoding="utf-8")

            job = ckit.JobItem(__read, __write)
            window.taskEnqueue(job, create_new_queue=False)

        pane = CPane()
        paths = pane.selectedItemPaths
        if len(paths) < 1:
            paths = [pane.focusedItemPath]

        for path in paths:
            _convert(path)

    class RuledDir:
        sep = "_"

        def __init__(self) -> None:
            self.pane = CPane()
            self.reg = re.compile(r"^[0-9]+")
            self.dirnames = [d.getName() for d in self.pane.dirs]

        def candidates(self) -> List[str]:
            return [
                "#_prepare",
                "#_main",
                "#_finished",
            ]

        @classmethod
        def _to_prefix(cls, s: str) -> str:
            if s.endswith(cls.sep):
                return s
            if cls.sep in s:
                return s[: s.rfind(cls.sep)] + cls.sep
            return s

        def _prefixes(self) -> List[str]:
            return [self._to_prefix(d) for d in self.dirnames]

        @classmethod
        def _to_suffix(cls, s: str) -> str:
            if s.startswith(cls.sep):
                return s
            if cls.sep in s:
                return s[s.find(cls.sep) :]
            return s

        def _suffixes(self) -> List[str]:
            return [self._to_suffix(d) for d in self.dirnames]

        def _remove_existing(self) -> List[str]:
            menu = []
            sufs = self._suffixes()
            pres = self._prefixes()
            for m in self.candidates():
                root = m.replace("/", os.sep).split(os.sep)[0]
                if self._to_prefix(root) in pres or self._to_suffix(root) in sufs:
                    continue
                menu.append(m)
            return menu

        def _increment(self) -> str:
            idx = -1
            idx_width = 1
            for d in self.dirnames:
                if m := self.reg.match(d):
                    n = m.group(0)
                    idx = max(idx, int(n))
                    idx_width = max(idx_width, len(n))
            idx += 1
            return str(idx).rjust(idx_width, "0")

        def listup(self) -> List[str]:
            menu = self._remove_existing()
            if any([dn.startswith("#") for dn in menu]):
                idx = self._increment()
                return [idx + dn[1:] for dn in menu]
            return menu

    # https://gist.github.com/AWtnb/db70a72f379e5d7307145177cc114141
    class BookProjectDir(RuledDir):
        def __init__(self) -> None:
            super().__init__()

        def get_parents(self, step: int) -> Tuple[str]:
            found = []
            p = Path(self.pane.currentPath)
            for _ in range(step):
                found.insert(0, p.name)
                p = p.parent
            return tuple(found)

        def candidates(self) -> List[str]:
            if smart_check_path(os.path.join(self.pane.currentPath, ".root")):
                return [
                    "_legacy",
                    "_wiki",
                    "design_装幀",
                    "donation_献本",
                    "galley_ゲラ",
                    "letter_手紙",
                    "meeting_会合",
                    "payment_印税",
                    "permission_許諾",
                    "projectpaper_企画書",
                    "promote_販宣",
                    "websupport",
                    "written_お原稿",
                ]

            galley_dirnames = [
                "#_layout_割付",
                "#_初校/0_plain",
                "#_再校/0_plain",
                "#_三校/0_plain",
                "#_念校/0_plain",
            ]
            appendix_dirnames = [
                "author_著者紹介",
                "toc_目次",
                "intro_はしがき",
                "intro_まえがき",
                "intro_はじめに",
                "postscript_あとがき",
                "postscript_おわりに",
                "reference_文献リスト",
                "index_索引",
                "endroll_奥付",
            ]
            appendix_dirnames = [n + "/0_layout_割付" for n in appendix_dirnames]

            mapping = {
                (
                    "juhan",
                    "?????_*",
                    "*",
                ): [
                    "#_send_to_author",
                    "#_reaction_from_author",
                    "#_send_to_printshop",
                ],
                ("galley_*",): [
                    "main_本文",
                    "appendix_付き物",
                ],
                ("galley_*", "main_*"): galley_dirnames,
                ("appendix_*",): appendix_dirnames,
                ("appendix_*", "*"): galley_dirnames,
                ("*_*校",): [
                    "#_plain",
                    "#_proofed",
                    "#_send_to_author",
                    "#_proofed_by_author",
                    "#_send_to_printshop",
                ],
                ("*_layout_*",): [
                    "document_入稿書類",
                    "mockup_見本組",
                    "send_to_printshop_入稿データ",
                ],
                ("*_layout_*", "send_to_printshop_*"): ["scan"],
                ("*_layout_*", "document_*"): [
                    "layout_レイアウト見本",
                    "mockup_見本組",
                ],
                ("donation_*",): ["letter_献本同封手紙", "usage_発送依頼書"],
                ("meeting_*", "*"): [
                    "#_事前資料",
                    "#_会合メモ",
                    "#_議事録",
                ],
                ("projectpaper_*",): [
                    "#_企画部会提出",
                    "#_修正反映",
                ],
                ("written_*",): ["_order_依頼書類"],
                ("written_*", "_order_*"): ["outline_執筆要領"],
            }

            for parents, names in mapping.items():
                ps = self.get_parents(len(parents))
                if all([fnmatch.fnmatch(p, parents[i]) for i, p in enumerate(ps)]):
                    return names

            return []

    def ruled_mkdir() -> None:
        menu = BookProjectDir().listup()
        if len(menu) < 1:
            smart_mkdir()
            return

        def _listup_dirnames(
            update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
        ) -> tuple:
            found = [
                name
                for name in menu
                if name.lower().startswith(update_info.text.lower())
            ]
            return found, 0

        placeholder = menu[0]
        name = stringify(
            window.commandLine(
                "DirName",
                text=placeholder,
                selection=[0, len(placeholder)],
                candidate_handler=_listup_dirnames,
                auto_complete=True,
            )
        )
        if 0 < len(name):
            CPane().mkdir(name)

    Keybinder().bind(ruled_mkdir, "S-A-N")

    class zyw:
        exe_path = shutil.which("zyw.exe")

        @classmethod
        def check(cls) -> bool:
            return cls.exe_path is not None

        @staticmethod
        def get_root(src: str) -> str:
            for path in Path(src).parents:
                p = os.path.join(path, ".root")
                if smart_check_path(p, 0.5):
                    return str(path)
            return src

        @classmethod
        def invoke(cls, current_dir: bool, search_all: bool) -> CallbackFunc:

            def _wrapper() -> None:
                pane = CPane()
                if pane.isBlank:
                    return

                def __find(job_item: ckit.JobItem) -> None:
                    job_item.result = None
                    if not cls.check():
                        Kiritori.log("Exe not found: '{}'".format(cls.exe_path))
                        return
                    root = (
                        pane.currentPath
                        if current_dir
                        else cls.get_root(pane.currentPath)
                    )
                    cmd = [
                        cls.exe_path,
                        "-exclude=_obsolete,node_modules",
                        "-all={}".format(search_all),
                        "-root={}".format(root),
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

                def __open(job_item: ckit.JobItem) -> None:
                    result = job_item.result
                    if result:
                        pane = CPane()
                        pane.openPath(result)

                job = ckit.JobItem(__find, __open)
                window.taskEnqueue(job, create_new_queue=False)

            return _wrapper

    def setup_zyw() -> None:
        for key, params in {
            "S-Z": (False, False),
            "Z": (False, True),
            "S-F": (True, False),
            "C-F": (True, True),
        }.items():
            Keybinder().bind(zyw().invoke(*params), key)

    setup_zyw()

    def concatenate_pdf() -> None:
        exe_path = shutil.which("go-pdfconc.exe")
        if not exe_path:
            return

        pane = CPane()
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

    def make_internet_shortcut(url: str = "") -> None:
        if not url.startswith("http"):
            Kiritori.log("invalid url: '{}'".format(url))
            return

        def _access(job_item: ckit.JobItem) -> None:
            job_item.body = None
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req) as res:
                    body = res.read()
                    try:
                        text = body.decode("utf-8", errors="ignore")
                    except Exception:
                        text = body.decode("cp932", errors="ignore")
                    job_item.body = text
            except Exception as e:
                Kiritori.log(e)

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
                    text="{} - {}".format(title, domain),
                    selection=[0, len(title)],
                )
            )
            if len(name) < 1:
                print("Canceled.\n")
                return
            lines.append("URL={}".format(url))
            if not name.endswith(".url"):
                name = name + ".url"
            Path(CPane().currentPath, name).write_text(
                "\n".join(lines), encoding="utf-8"
            )

        job = ckit.JobItem(_access, _make_shortcut)
        window.taskEnqueue(job, create_new_queue=False)

    def on_paste() -> None:
        c = ckit.getClipboardText()
        if len(c) < 1:
            save_clipboard_image_as_file()
            return
        if c.startswith("http"):
            make_internet_shortcut(c)
            return
        CPane().openPath(c.strip().strip('"'))

    Keybinder().bind(on_paste, "C-V", "S-Insert")

    class DriveHandler:

        def __init__(self) -> None:
            pane = CPane()
            self._current_drive = Path(pane.currentPath).drive

        def listup(self, include_current: bool = False) -> List[str]:
            drives = []
            for d in ckit.getDrives():
                d += ":"
                if d == self._current_drive and not include_current:
                    continue
                detail = ckit.getDriveDisplayName(d)
                drives.append(d + detail[: detail.rfind("(")])
            return drives

        def parse(self, s: str) -> str:
            sep = ":"
            if sep in s:
                return s[: s.find(sep) + 1]
            return s

    def change_drive() -> None:
        pane = CPane()

        drive_handler = DriveHandler()
        drives = drive_handler.listup()

        def _listup_drives(
            update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
        ) -> tuple:
            found = [
                d for d in drives if d.lower().startswith(update_info.text.lower())
            ]
            return found, 0

        result = stringify(
            window.commandLine(
                title="ChangeDrive",
                candidate_handler=_listup_drives,
                auto_complete=True,
            )
        )
        result = drive_handler.parse(result)
        if len(result) < 1:
            return
        if result == "C:":
            pane.openPath(DESKTOP_PATH)
            return
        pane.openPath(result)

    Keybinder().bind(change_drive, "D")

    def jump_input() -> None:
        pane = CPane()

        def _listup_names(update_info: ckit.ckit_widget.EditWidget.UpdateInfo) -> tuple:
            found = [
                name
                for name in pane.names
                if name.lower().startswith(update_info.text.lower())
            ]
            return found, 0

        result = stringify(
            window.commandLine(
                title="JumpInput",
                candidate_handler=_listup_names,
                auto_complete=True,
            )
        )

        if 0 < len(result):
            pane.openPath(os.path.join(pane.currentPath, result))

    Keybinder().bind(jump_input, "F")

    def eject_current_drive() -> None:
        pane = CPane()
        current = pane.currentPath
        if current.startswith("C:"):
            return

        current_drive = Path(current).drive
        other = CPane(False)
        if other.currentPath.startswith(current_drive):
            other.openPath(DESKTOP_PATH)

        pane.openPath(DESKTOP_PATH)

        def _eject(job_item: ckit.JobItem) -> None:
            job_item.result = None
            cmd = (
                "PowerShell -NoProfile -Command "
                '$driveEject = New-Object -comObject Shell.Application; $driveEject.Namespace(17).ParseName("""{}\\""").InvokeVerb("""Eject""");Start-Sleep -Seconds 2'.format(
                    current_drive
                )
            )
            proc = subprocess.run(
                cmd, creationflags=subprocess.CREATE_NO_WINDOW, shell=True
            )
            if proc.returncode != 0:
                if o := proc.stdout:
                    Kiritori.log(o)
                if e := proc.stderr:
                    Kiritori.log(e)
                return
            job_item.result = "Ejected drive '{}'".format(current_drive)

        def _finished(job_item: ckit.JobItem) -> None:
            if job_item.result is None:
                pane.openPath(current)
                Kiritori.log("Failed to eject drive '{}'".format(current_drive))
            else:
                Kiritori.log(job_item.result)

        job = ckit.JobItem(_eject, _finished)
        window.taskEnqueue(job, create_new_queue=False)

    def compress_with_7zip(zip_path: str, *targets: str) -> None:
        seven_zip = shutil.which("7z")
        if seven_zip is None:
            Kiritori.log("7z not found.")
            return

        def _compress(_) -> None:
            try:
                cmd = [seven_zip, "a", "-tzip", "-y", zip_path] + list(targets)
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if proc.returncode != 0:
                    if o := proc.stdout:
                        Kiritori.log(o)
                    if e := proc.stderr:
                        Kiritori.log(e)
            except Exception as e:
                Kiritori.log(e)
                return

        def _finished(_) -> None:
            pass

        job = ckit.JobItem(_compress, _finished)
        window.taskEnqueue(job, create_new_queue=False)

    def compress_files() -> None:
        pane = CPane()
        targets = pane.selectedItemPaths

        if len(targets) < 1:
            return

        placeholder = datetime.datetime.today().strftime("%Y%m%d-%H%M%S")
        if len(targets) == 1:
            placeholder = Path(targets[0]).name

        result = stringify(window.commandLine("Zip name", text=placeholder))
        if len(result) < 1:
            return
        if not result.endswith(".zip"):
            result += ".zip"

        if pane.byName(result) != -1:
            Kiritori.log("'{}' already exists.".format(result))
            return

        zip_path = os.path.join(pane.currentPath, result)

        if shutil.which("7z") is not None:
            compress_with_7zip(zip_path, *targets)
        else:
            pane.adjustWidth()
            window.command_CreateArchive(None)

    def extract_with_7zip(dest: str, *paths: str) -> None:
        seven_zip = shutil.which("7z")
        if seven_zip is None:
            Kiritori.log("7z not found.")
            return

        targets = [
            t for t in paths if Path(t).is_file() and is_extractable(Path(t).suffix)
        ]
        if len(targets) < 1:
            return

        def _extract(_) -> None:
            for target in targets:
                try:
                    cmd = [
                        seven_zip,
                        "x",
                        target,
                        "-o{}".format(dest),
                        "-y",
                    ]
                    proc = subprocess.run(
                        cmd,
                        capture_output=True,
                        text=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                    if proc.returncode != 0:
                        if o := proc.stdout:
                            Kiritori.log(o)
                        if e := proc.stderr:
                            Kiritori.log(e)
                except Exception as e:
                    Kiritori.log(e)
                    return

        def _finished(_) -> None:
            pass

        job = ckit.JobItem(_extract, _finished)
        window.taskEnqueue(job, create_new_queue=False)

    def extract_archives() -> None:
        pane = CPane()

        for item in pane.selectedItems:
            ext = Path(item.getFullpath()).suffix
            if not is_extractable(ext):
                pane.unSelectByName(item.getName())

        if not pane.hasSelection:
            return

        placeholder = "extract_{}".format(
            datetime.datetime.today().strftime("%Y%m%d-%H%M%S")
        )
        if len(pane.selectedItems) == 1:
            p = pane.selectedItemPaths[0]
            placeholder = Path(p).stem

        result = stringify(
            window.commandLine(
                "Extract as",
                text=placeholder,
            )
        )
        if len(result) < 1:
            return

        if pane.byName(result) != -1:
            Kiritori.log("'{}' already exists.".format(result))
            return

        pane.mkdir(result, False)
        extract_path = os.path.join(pane.currentPath, result)

        if shutil.which("7z") is not None:
            extract_with_7zip(extract_path, *pane.selectedItemPaths)
        else:
            pane.adjustWidth()
            CPane(False).openPath(extract_path)
            window.command_ExtractArchive(None)

    def recylcebin() -> None:
        shell_exec("shell:RecycleBinFolder")

    Keybinder().bind(recylcebin, "Delete")

    def copy_current_path() -> None:
        pane = CPane()
        p = pane.currentPath
        ckit.setClipboardText(p)
        window.setStatusMessage("copied current path: '{}'".format(p), 3000)

    Keybinder().bind(copy_current_path, "C-A-P")

    def on_copy() -> None:
        selection_left, selection_right = window.log_pane.selection
        if selection_left != selection_right:
            window.command_SetClipboard_LogSelected(None)
            return

        pane = CPane()

        targets = []
        if pane.isBlank:
            targets.append(pane.currentPath)
        else:
            targets = pane.selectedItemPaths
            if len(targets) < 1:
                targets.append(pane.focusedItemPath)

        menu = ["Fullpath", "Name"]
        if any([Path(t).is_file() for t in targets]):
            menu.append("Basename")

        if all([Path(path).suffix in [".docx", ".xlsx"] for path in targets]):
            menu.append("Text content")

        result, _ = invoke_listwindow("Copy", menu)
        if result < 0:
            return

        def _from(path: str) -> str:
            if result == 0:
                return path
            p = Path(path)
            if result == 1:
                return p.name
            if result == 3:
                content = read_openxml(path)
                return content
            return p.stem

        def _copy(job_item: ckit.JobItem) -> None:
            lines = [_from(target) for target in targets]
            ckit.setClipboardText("\n".join(lines))
            job_item.count = len(lines)

        def _finished(job_item: ckit.JobItem) -> None:
            s = "Copied {} of ".format(menu[result])
            if 1 < job_item.count:
                s += "{} items.".format(job_item.count)
            else:
                s += "'{}'.".format(Path(targets[0]).name)
            Kiritori.log(s)

        job = ckit.JobItem(_copy, _finished)
        window.taskEnqueue(job, create_new_queue=False)

    Keybinder().bind(on_copy, "C-C")

    class Selector:
        @staticmethod
        def allItems() -> None:
            CPane().selectAll()

        @staticmethod
        def clear() -> None:
            pane = CPane()
            pane.unSelect(pane.cursor)

        @staticmethod
        def toggleAll() -> None:
            pane = CPane()
            for i in range(pane.count):
                pane.toggleSelection(i)

        @staticmethod
        def toTop() -> None:
            pane = CPane()
            if pane.cursor < pane.selectionTop:
                for i in range(pane.count):
                    if i <= pane.cursor:
                        pane.select(i)
            else:
                for item in pane.selectedOrAllItems:
                    i = pane.byName(item.getName())
                    if i <= pane.cursor:
                        pane.toggleSelection(i)

        @staticmethod
        def clearToTop() -> None:
            pane = CPane()
            for i in range(pane.count):
                if i <= pane.cursor:
                    pane.unSelect(i)

        @staticmethod
        def toBottom() -> None:
            pane = CPane()
            if pane.selectionBottom < pane.cursor:
                for i in range(pane.count):
                    if pane.cursor <= i:
                        pane.select(i)
            else:
                for item in pane.selectedOrAllItems:
                    i = pane.byName(item.getName())
                    if pane.cursor <= i:
                        pane.toggleSelection(i)

        @staticmethod
        def clearToBottom() -> None:
            pane = CPane()
            for i in range(pane.count):
                if pane.cursor < i:
                    pane.unSelect(i)

        @staticmethod
        def files() -> None:
            pane = CPane()
            for item in pane.selectedOrAllItems:
                name = item.getName()
                if not item.isdir():
                    pane.toggleSelection(pane.byName(name))

        @staticmethod
        def dirs() -> None:
            pane = CPane()
            for item in pane.selectedOrAllItems:
                name = item.getName()
                if item.isdir():
                    pane.toggleSelection(pane.byName(name))

        @staticmethod
        def clearAll() -> None:
            CPane().unSelectAll()

        @staticmethod
        def byFunction(func: Callable[[str], bool], negative: bool = False) -> None:
            pane = CPane()
            for item in pane.selectedOrAllItems:
                path = item.getFullpath()
                if (negative and not func(path)) or (not negative and func(path)):
                    name = item.getName()
                    pane.toggleSelection(pane.byName(name))

        @classmethod
        def byExtension(cls, s: str, negative: bool = False) -> None:
            def _checkPath(path: str) -> bool:
                return Path(path).suffix == s

            cls.byFunction(_checkPath, negative)

        @classmethod
        def stemContains(cls, s: str, negative: bool = False) -> None:
            def _checkPath(path: str) -> bool:
                return s in Path(path).stem

            cls.byFunction(_checkPath, negative)

        @classmethod
        def stemStartsWith(cls, s: str, negative: bool = False) -> None:
            def _checkPath(path: str) -> bool:
                return Path(path).stem.startswith(s)

            cls.byFunction(_checkPath, negative)

        @classmethod
        def stemEndsWith(cls, s: str, negative: bool = False) -> None:
            def _checkPath(path: str) -> bool:
                return Path(path).stem.endswith(s)

            cls.byFunction(_checkPath, negative)

        @classmethod
        def stemMatches(cls, s: str, case: bool, negative: bool = False) -> None:
            reg = re.compile(s) if case else re.compile(s, re.IGNORECASE)

            def _checkPath(path: str) -> bool:
                return reg.search(Path(path).stem) is not None

            cls.byFunction(_checkPath, negative)

        @classmethod
        def apply(cls) -> None:
            for k, v in {
                "C-A": cls.allItems,
                "U": cls.clearAll,
                "Esc": cls.clearAll,
                "A-F": cls.files,
                "A-D": cls.dirs,
                "S-Home": cls.toTop,
                "S-A": cls.toTop,
                "S-End": cls.toBottom,
                "S-E": cls.toBottom,
            }.items():
                Keybinder().bind(v, k)

    Selector().apply()

    def unselect_panes() -> None:
        CPane().unSelectAll()
        CPane(False).unSelectAll()

    Keybinder().bind(unselect_panes, "C-U", "S-Esc")

    def to_edge_dir() -> None:
        pane = CPane()
        if len(pane.dirs) < 1:
            return

        root = pane.currentPath

        print("Searching for last-indexed dir under '{}' ...".format(pane.currentPath))

        def _traverse(job_item: ckit.JobItem) -> None:
            job_item.result = None
            if pane.isBlank:
                return

            paths = []
            for item in pane.traverse(False, "_obsolete"):
                if item.isdir():
                    rel = item.getName()
                    if any([(os.sep + c in rel) for c in ("_", "~")]):
                        continue
                    paths.append(item.getFullpath())

            if 0 < len(paths):
                paths.sort()
                job_item.result = paths[-1]

        def _open(job_item: ckit.JobItem) -> None:
            if job_item.result:
                pane.openPath(job_item.result)
                show_path_tree(job_item.result)

        job = ckit.JobItem(_traverse, _open)
        window.taskEnqueue(job, create_new_queue=False)

    Keybinder().bind(to_edge_dir, "A-L")

    def to_root_of_index() -> None:
        pane = CPane()
        reg = re.compile(r"^\d+_|^\d+$")
        root = None
        f = "_" if pane.isBlank else pane.focusedItem.getName()
        for parent in Path(pane.currentPath, f).parents:
            if reg.match(parent.name):
                root = parent
                break
        if root:
            root = str(root.parent)
            if root != pane.currentPath:
                pane.openPath(root)

    Keybinder().bind(to_root_of_index, "A-H")

    class SmartJumper:

        def __init__(self, by_prefix: bool):
            self.pane = CPane()
            self.dests = self.prefixEdges() if by_prefix else self.itemEdges()

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

        def appendBaseEdges(self, edges: List[int]) -> List[int]:
            edges.append(0)
            edges.append(self.pane.count - 1)
            if 0 < (nd := len(self.pane.dirs)):
                edges.append(nd - 1)
                if 0 < len(self.pane.files):
                    edges.append(nd)
            return edges

        def itemEdges(self) -> List[int]:
            if self.pane.isBlank:
                return []
            stack = []
            for i in range(self.pane.count):
                item = self.pane.byIndex(i)
                if item.bookmark() or item.selected():
                    stack.append(i)
            stack = self.getBlockEdges(stack)
            return sorted(list(set(self.appendBaseEdges(stack))))

        def prefixEdges(self) -> List[int]:
            if self.pane.isBlank:
                return []
            names = self.pane.names
            if len(names) < 2:
                return []
            prefs = [name.split("_", 1)[0] for name in names]
            edges = []
            start = 0
            for i in range(1, len(prefs) + 1):
                if i == len(prefs) or prefs[i] != prefs[start]:
                    if 1 < i - start:
                        edges += [start, i - 1]
                    start = i
            return sorted(list(set(self.appendBaseEdges(edges))))

        def down(self, selecting: bool) -> None:
            if len(self.dests) < 1:
                return
            cur = self.pane.cursor
            idx = -1
            for t in self.dests:
                if cur < t:
                    idx = t
                    break
            if idx < 0:
                return
            if selecting:
                for i in range(self.pane.count):
                    if cur <= i and i <= idx:
                        self.pane.select(i)
            self.pane.focus(idx)

        def up(self, selecting: bool) -> None:
            if len(self.dests) < 1:
                return
            cur = self.pane.cursor
            idx = -1
            for t in self.dests:
                if t < cur:
                    idx = t
            if idx < 0:
                return
            if selecting:
                for i in range(self.pane.count):
                    if idx <= i and i <= cur:
                        self.pane.select(i)
            self.pane.focus(idx)

    def smart_jumpDown(by_prefix: bool, selecting: bool) -> CallbackFunc:

        def _jumper() -> None:
            SmartJumper(by_prefix).down(selecting)

        return _jumper

    Keybinder().bind(smart_jumpDown(True, False), "A-J")
    Keybinder().bind(smart_jumpDown(True, True), "S-A-J")
    Keybinder().bind(smart_jumpDown(False, False), "C-J")
    Keybinder().bind(smart_jumpDown(False, True), "S-C-J")

    def smart_jumpUp(by_prefix: bool, selecting: bool) -> CallbackFunc:

        def _jumper() -> None:
            SmartJumper(by_prefix).up(selecting)

        return _jumper

    Keybinder().bind(smart_jumpUp(True, False), "A-K")
    Keybinder().bind(smart_jumpUp(True, True), "S-A-K")
    Keybinder().bind(smart_jumpUp(False, False), "C-K")
    Keybinder().bind(smart_jumpUp(False, True), "S-C-K")

    def duplicate_pane() -> None:
        window.command_ChdirInactivePaneToOther(None)
        pane = CPane()
        pane.focusOther()

    Keybinder().bind(duplicate_pane, "W")

    def open_on_explorer() -> None:
        pane = CPane(True)
        shell_exec(pane.currentPath)

    Keybinder().bind(open_on_explorer, "C-S-E")

    def open_to_other() -> None:
        pane = CPane(True)
        if not pane.isBlank:
            CPane(False).openPath(pane.focusedItemPath)
            pane.focusOther()

    Keybinder().bind(open_to_other, "S-L")

    def open_parent_to_other() -> None:
        pane = CPane(True)
        parent, current_name = os.path.split(pane.currentPath)
        CPane(False).openPath(parent, current_name)
        pane.focusOther()

    Keybinder().bind(open_parent_to_other, "S-U", "S-H")

    def on_vscode() -> None:
        pane = CPane()
        open_vscode(pane.currentPath)

    Keybinder().bind(on_vscode, "V")

    class Renamer:
        def __init__(self) -> None:
            self._pane = CPane()

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
                window.subThreadCall(org_path.rename, (str(new_path),))
                print("Renamed: {}\n     ==> {}\n".format(org_path.name, new_name))
                self._pane.refresh()
                if focus:
                    self._pane.focusByName(new_name)
            except Exception as e:
                print(e)

    class RenameConfig:
        ini_section = "RENAME_CONFIG"

        def __init__(self, option_name: str) -> None:
            try:
                window.ini.add_section(self.ini_section)
            except configparser.DuplicateSectionError:
                pass
            self._option_name = option_name

        def register(self, value: str) -> None:
            window.ini.set(self.ini_section, self._option_name, value)

        @property
        def value(self) -> str:
            try:
                return window.ini.get(self.ini_section, self._option_name)
            except:
                return ""

    class RenameInfo(NamedTuple):
        orgPath: Path
        newName: str

    def rename_substr() -> None:
        renamer = Renamer()

        targets = renamer.candidate
        if len(targets) < 1:
            return

        placeholder = ";-1"
        sel_end = 0

        rename_config_substr = RenameConfig("substr")
        if 0 < len(last := rename_config_substr.value):
            placeholder = last
            sel_end = last.find(";")

        print("Rename substring (extract part of filename):")
        rename_command = stringify(
            window.commandLine(
                "Offset[;Length]", text=placeholder, selection=[0, sel_end]
            )
        )

        if len(rename_command) < 1:
            print("Canceled.\n")
            return

        sep = ";"
        if sep not in rename_command:
            rename_command += ";-1"
        else:
            if rename_command.startswith(sep):
                rename_command = "0" + rename_command

        offset = int(rename_command[: rename_command.find(sep)])
        length = int(rename_command[rename_command.rfind(sep) + 1 :])

        if offset == 0 and length == -1:
            print("Canceled.\n")
            return

        rename_config_substr.register(rename_command)

        def _confirm() -> Tuple[List[RenameInfo], bool]:
            infos = []
            lines = []
            for item in targets:
                org_path = Path(item.getFullpath())

                def _get_new_stem() -> str:
                    stem = org_path.stem
                    if length < 0:
                        if length == -1:
                            return stem[offset:]
                        return stem[offset : length + 1]
                    return stem[offset : offset + length]

                new_name = _get_new_stem() + org_path.suffix
                infos.append(RenameInfo(org_path, new_name))
                lines.append("Rename: {}\n    ==> {}\n".format(org_path.name, new_name))

            lines.append(
                "\noffset: {}\nlength: {}\nOK? (Enter / Esc)".format(offset, length)
            )

            return infos, popResultWindow(window, "Preview", "\n".join(lines))

        infos, ok = _confirm()
        if len(infos) < 1 or not ok:
            print("Canceled.\n")
            return

        def _func() -> None:
            for info in infos:
                renamer.execute(info.orgPath, info.newName)

        Kiritori.wrap(_func)

    Keybinder().bind(rename_substr, "S-S")

    def rename_insert() -> None:
        renamer = Renamer()

        targets = renamer.candidate
        if len(targets) < 1:
            return

        placeholder = "@-1"
        sel_end = 0

        rename_config_insert = RenameConfig("insert")
        last_insert = rename_config_insert.value
        if 0 < len(last_insert):
            placeholder = last_insert
            sel_end = last_insert.find("@")

        print("Rename insert:")
        rename_command = stringify(
            window.commandLine(
                "Text[@position]", text=placeholder, selection=[0, sel_end]
            ),
            False,
        ).rstrip()

        if len(rename_command) < 1:
            print("Canceled.\n")
            return

        sep = "@"
        if rename_command.startswith(sep):
            print("Canceled.\n")
            return

        if sep not in rename_command:
            rename_command += "@-1"
        else:
            if rename_command.endswith(sep):
                rename_command += "-1"

        rename_config_insert.register(rename_command)

        ins = rename_command[: rename_command.rfind(sep)]
        pos = int(rename_command[rename_command.rfind(sep) + 1 :])

        def _confirm() -> Tuple[List[RenameInfo], bool]:
            infos = []
            lines = []
            for item in targets:
                org_path = Path(item.getFullpath())

                def _get_new_stem() -> str:
                    stem = org_path.stem
                    if pos < 0:
                        if pos == -1:
                            return stem + ins
                        p = pos + 1
                        return stem[:p] + ins + stem[p:]
                    return stem[:pos] + ins + stem[pos:]

                new_name = _get_new_stem() + org_path.suffix
                infos.append(RenameInfo(org_path, new_name))
                lines.append("Rename: {}\n    ==> {}\n".format(org_path.name, new_name))

            lines.append("\ninsert: {}\nat: {}\nOK? (Enter / Esc)".format(ins, pos))

            return infos, popResultWindow(window, "Preview", "\n".join(lines))

        infos, ok = _confirm()
        if len(infos) < 1 or not ok:
            print("Canceled.\n")
            return

        def _func() -> None:
            for info in infos:
                renamer.execute(info.orgPath, info.newName)

        Kiritori.wrap(_func)

    Keybinder().bind(rename_insert, "S-I")

    class PhotoFile:
        def __init__(self, path: str):
            self.path = path
            _, self.name = os.path.split(self.path)
            _, self.ext = os.path.splitext(self.name)
            self.filler = datetime.datetime.fromtimestamp(0)

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
                        return self.filler
                    for tag_id, value in exif_data.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if tag == "DateTimeOriginal":
                            dt = datetime.datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                            return dt
                    return self.filler
            except Exception as e:
                print(e)
                return self.filler

        def get_timestamp(self) -> datetime.datetime:
            offset = self.get_byte_offset()
            if offset < 1:
                if offset == 0:
                    return self.from_exif()
                return self.filler
            with open(self.path, "rb") as f:
                f.seek(offset)
                bytes_read = f.read(19)
            decoded = bytes_read.decode("ascii")
            return datetime.datetime.strptime(decoded, "%Y:%m:%d %H:%M:%S")

        def rename(self, fmt: str) -> str:
            ts = self.get_timestamp().strftime(fmt)
            return ts + "_" + self.name

    def rename_photo_file() -> None:
        renamer = Renamer()

        targets = []
        for item in renamer.candidate:
            if not item.isdir():
                targets.append(item)

        if len(targets) < 1:
            return

        def _confirm() -> Tuple[List[RenameInfo], bool]:
            infos = []
            lines = []
            for item in targets:
                path = item.getFullpath()
                photo = PhotoFile(path)
                new_name = photo.rename("%Y_%m%d_%H%M%S00")
                infos.append(RenameInfo(Path(path), new_name))
                lines.append(
                    "Rename: {}\n    ==> {}\n".format(item.getName(), new_name)
                )

            lines.append("\ninsert timestamp:\nOK? (Enter / Esc)")

            return infos, popResultWindow(window, "Preview", "\n".join(lines))

        infos, ok = _confirm()
        if len(infos) < 1 or not ok:
            print("Canceled.\n")
            return

        def _func() -> None:
            for info in infos:
                renamer.execute(info.orgPath, info.newName)

        Kiritori.wrap(_func)

    def rename_lightroom_photo_from_dropbox() -> None:
        renamer = Renamer()

        targets = []
        for item in renamer.candidate:
            if not item.isdir():
                targets.append(item)

        if len(targets) < 1:
            return

        def _confirm() -> Tuple[List[RenameInfo], bool]:
            infos = []
            lines = []
            for item in targets:
                path = item.getFullpath()
                p = Path(path)
                elems = p.stem.replace("写真 ", "").split(" ")
                date_ts = elems[0].replace("-", "")
                time_ts = "".join([str(n).rjust(2, "0") for n in elems[1:4]])
                if 4 < len(elems):
                    time_ts = (
                        time_ts + "-" + elems[-1].replace("(", "").replace(")", "")
                    )
                new_name = date_ts + "-IMG_" + time_ts + p.suffix
                infos.append(RenameInfo(p, new_name))
                lines.append(
                    "Rename: {}\n    ==> {}\n".format(item.getName(), new_name)
                )

            lines.append("\ninsert timestamp:\nOK? (Enter / Esc)")

            return infos, popResultWindow(window, "Preview", "\n".join(lines))

        infos, ok = _confirm()
        if len(infos) < 1 or not ok:
            print("Canceled.\n")
            return

        def _func() -> None:
            for info in infos:
                renamer.execute(info.orgPath, info.newName)

        Kiritori.wrap(_func)

    def rename_index() -> None:
        renamer = Renamer()

        targets = renamer.candidate
        if len(targets) < 1:
            return

        placeholder = "01@-1,1;_;"
        rename_config_index = RenameConfig("index")
        last_value = rename_config_index.value
        if 0 < len(last_value):
            placeholder = last_value

        print("Rename insert index:")
        rename_command = stringify(
            window.commandLine(
                "Index[@position,step,skips1,skips2,...;connector;newstem]",
                text=placeholder,
                selection=[0, 2],
            ),
            trim=False,
        )

        if len(rename_command) < 1:
            print("Canceled.\n")
            return

        sep = ";"
        if sep not in rename_command:
            rename_command += sep * 2
        else:
            if len(rename_command.split(sep)) < 3:
                rename_command += sep

        command_index, connector, command_newstem = rename_command.split(sep)[:3]

        class NameIndex:
            position = -1
            step = 1
            skips = []

            def __init__(self) -> None:
                commands = command_index.split("@")
                left_parts = commands[0].rstrip()
                if str(left_parts).isdecimal():
                    self.index_template = left_parts
                else:
                    self.index_template = "00"
                if 1 < len(commands):
                    args = [a.strip() for a in commands[1].split(",")]
                    self.position = int(args[0])
                    if 1 < len(args):
                        self.step = int(args[1])
                    if 2 < len(args):
                        self.skips = [int(a) for a in args[2:]]

                c = self.index_template[0]
                if c in "123456789":
                    self.filler = ""
                else:
                    self.filler = c

            def fill(self, i: int) -> str:
                s = str(i)
                w = len(self.index_template)
                filled = s if len(self.filler) < 1 else s.rjust(w, self.filler)
                if self.position < 0:
                    return connector + filled
                return filled + connector

            @property
            def start(self) -> int:
                return int(self.index_template)

            def increment(self, i: int) -> int:
                i += self.step
                while 1:
                    if i not in self.skips:
                        break
                    i += self.step
                return i

        ni = NameIndex()

        print(rename_command)
        rename_config_index.register(rename_command)

        def _confirm() -> Tuple[List[RenameInfo], bool]:
            infos = []
            lines = []
            idx = ni.start
            for item in targets:
                org_path = Path(item.getFullpath())
                stem = org_path.stem if len(command_newstem) < 1 else command_newstem
                pos = ni.position
                if ni.position < 0:
                    pos = len(stem) + 1 + ni.position
                new_name = stem[:pos] + ni.fill(idx) + stem[pos:] + org_path.suffix
                idx = ni.increment(idx)
                infos.append(RenameInfo(org_path, new_name))
                lines.append("Rename: {}\n    ==> {}\n".format(org_path.name, new_name))

            lines.append(
                "\ninsert (start={}, step={}, skips={}):\nOK? (Enter / Esc)".format(
                    ni.start, ni.step, ni.skips
                )
            )

            return infos, popResultWindow(window, "Preview", "\n".join(lines))

        infos, ok = _confirm()
        if len(infos) < 1 or not ok:
            print("Canceled.\n")
            return

        def _func() -> None:
            for info in infos:
                renamer.execute(info.orgPath, info.newName)

        Kiritori.wrap(_func)

    Keybinder().bind(rename_index, "A-S-I")

    def rename_regexp() -> None:
        renamer = Renamer()

        targets = renamer.candidate
        if len(targets) < 1:
            return

        placeholder = "/"
        sel_end = 0

        rename_config_regexp = RenameConfig("regexp")
        last_regexp = rename_config_regexp.value
        if 0 < len(last_regexp):
            placeholder = last_regexp
            sel_end = max(last_regexp.find("/"), 0)

        print("Rename with regexp-replace. Trailing `/c` enables case-sensitive-mode")
        rename_command = window.commandLine(
            "[regexp]/[replace with](/c)", text=placeholder, selection=[0, sel_end]
        )

        if not rename_command:
            print("Canceled.\n")
            return

        class RegCommand:
            sep = "/"

            def __init__(self, line: str) -> None:
                a = line.split(self.sep)
                if len(a) < 2:
                    a.append("")
                if len(a) < 3:
                    a.append("")
                self.args = a

            def is_valid(self) -> bool:
                return 0 < len(self.args[0])

            @property
            def search_reg(self) -> re.Pattern:
                r = self.args[0]
                if self.args[2] == "c":
                    return re.compile(r)
                return re.compile(r, re.IGNORECASE)

            @property
            def to_str(self) -> str:
                return self.args[1]

        rc = RegCommand(rename_command)
        if not rc.is_valid():
            print("Canceled (Invalid command).\n")
            return

        rename_config_regexp.register(rename_command)
        reg = rc.search_reg

        def _confirm() -> Tuple[List[RenameInfo], bool]:
            infos = []
            lines = []
            for item in targets:
                org_path = Path(item.getFullpath())
                new_name = reg.sub(rc.to_str, org_path.stem) + org_path.suffix
                if org_path.name != new_name:
                    infos.append(RenameInfo(org_path, new_name))
                    lines.append(
                        "Rename: {}\n    ==> {}\n".format(org_path.name, new_name)
                    )

            if len(lines) < 1:
                lines.append("Nothing will be renamed.")
            else:
                lines.append(
                    "\nregexp: {}\nnew text: {}\nOK? (Enter / Esc)".format(
                        reg, rc.to_str
                    )
                )

            return infos, popResultWindow(window, "Preview", "\n".join(lines))

        infos, ok = _confirm()
        if len(infos) < 1 or not ok:
            print("Canceled.\n")
            return

        def _func() -> None:
            for info in infos:
                renamer.execute(info.orgPath, info.newName)

        Kiritori.wrap(_func)

    Keybinder().bind(rename_regexp, "S-R")

    class NameAffix:
        sep = "_"

        def __init__(self) -> None:
            self.pane = CPane()

        @staticmethod
        def to_stem(path: str) -> str:
            _, name = os.path.split(path)
            stem, _ = os.path.splitext(name)
            return stem

        def selected_stems(self) -> List[str]:
            sels = self.pane.selectedItemPaths + CPane(False).selectedItemPaths
            return sorted([self.to_stem(sel) for sel in sels])

    class NamePrefix(NameAffix):
        def __init__(self) -> None:
            super().__init__()

        @classmethod
        def from_name(cls, s: str) -> List[str]:
            pres = []
            for i, c in enumerate(s):
                if 0 < i and c == cls.sep:
                    pres.append(s[: i + 1])
            return pres

        def variants(self) -> List[str]:
            pres = []
            for path in self.pane.paths:
                pres += self.from_name(self.to_stem(path))
            return pres

    class PrefixHandler(NamePrefix):
        def __init__(self) -> None:
            super().__init__()
            self.candidates = self.variants()
            self.selected = self.selected_stems()

        def filter_by(self, s: str) -> List[str]:
            return [pre for pre in self.candidates if pre.startswith(s)]

        def invoke(
            self,
        ) -> Callable[[ckit.ckit_widget.EditWidget.UpdateInfo], Tuple[List[str], int]]:

            def _handler(
                update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
            ) -> Tuple[List[str], int]:
                found = self.filter_by(update_info.text)
                return self.selected + sorted(list(set(found)), key=len), 0

            return _handler

    class NameSuffix(NameAffix):

        def __init__(
            self,
            with_timestamp: bool = False,
            additional: List[str] = [],
        ) -> None:
            super().__init__()
            self.timestamp = ""
            if with_timestamp:
                self.timestamp = datetime.datetime.today().strftime("%Y%m%d")

            self._additional = [self.sep + a for a in additional]

        @classmethod
        def from_name(cls, s: str) -> List[str]:
            sufs = []
            for i, c in enumerate(s):
                if 0 < i and c == cls.sep:
                    sufs.append(s[i:])
            return sufs

        def variants(self) -> List[str]:
            sufs = []
            for path in self.pane.paths:
                sufs += self.from_name(self.to_stem(path))
            if 0 < len(self._additional):
                sufs += self._additional
            if self.timestamp:
                if (s := self.sep + self.timestamp) not in sufs:
                    sufs = [s] + sufs
            return sufs

        def from_parents(self) -> List[str]:
            found = []
            parents = Path(self.pane.currentPath, "_").parents
            reg = re.compile(r"[0-9]{6,}")
            for parent in parents:
                if m := reg.search(parent.name):
                    found.append(self.sep + m.group(0))
                    break
            return found

    class SuffixHandler(NameSuffix):
        def __init__(self, with_timestamp: bool = False, additional: List[str] = []):
            super().__init__(with_timestamp, additional)
            self.selected = self.selected_stems()
            self.candidates = self.variants() + self.from_parents()

        def filter_by(self, s: str) -> List[str]:
            suffixes = self.candidates
            if self.sep not in s:
                return [s + suf for suf in suffixes]
            if s.endswith(self.sep):
                return [s + suf[1:] for suf in suffixes]
            found = []
            sep_pos = s.find(self.sep)
            command_suffix = s[sep_pos:]
            for suf in suffixes:
                if suf.startswith(command_suffix):
                    found.append(s[:sep_pos] + suf)
            return found

        def invoke(
            self,
        ) -> Callable[[ckit.ckit_widget.EditWidget.UpdateInfo], Tuple[List[str], int]]:

            def _filter(
                update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
            ) -> Tuple[List[str], int]:
                found = self.filter_by(update_info.text)
                return self.selected + sorted(list(set(found)), key=len), 0

            return _filter

    def name_candidate_handler(
        with_timestamp: bool,
    ) -> Callable[[ckit.ckit_widget.EditWidget.UpdateInfo], Tuple[List[str], int]]:
        prefix_handler = PrefixHandler()
        suffix_handler = SuffixHandler(with_timestamp)
        selected = NameAffix().selected_stems()

        def _handler(
            update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
        ) -> Tuple[List[str], int]:
            s = update_info.text
            found = (
                prefix_handler.filter_by(s)
                if NameAffix.sep not in s
                else suffix_handler.filter_by(s)
            )

            return selected + sorted(list(set(found)), key=len), 0

        return _handler

    def rename_stem() -> None:
        pane = CPane()
        item = pane.focusedItem

        renamer = Renamer()
        if not renamer.renamable(item) or pane.isBlank:
            return

        ts = item.time()
        item_timestamp = "{}{:02}{:02}".format(ts[0], ts[1], ts[2])
        additional_suffix = [item_timestamp]

        focused_path = Path(item.getFullpath())
        placeholder = focused_path.name if focused_path.is_dir() else focused_path.stem
        offset = len(placeholder)
        sel = [offset, offset]

        new_stem, mod = window.commandLine(
            title="NewStem",
            text=placeholder,
            selection=sel,
            candidate_handler=SuffixHandler(True, additional_suffix).invoke(),
            return_modkey=True,
        )

        new_stem = stringify(new_stem)
        if len(new_stem) < 1:
            return

        new_name = new_stem + focused_path.suffix

        def _func() -> None:
            renamer.execute(focused_path, new_name, mod == ckit.MODKEY_SHIFT)

        Kiritori.wrap(_func)

    Keybinder().bind(rename_stem, "N")

    def rename_ext() -> None:
        pane = CPane()
        item = pane.focusedItem
        if item.isdir():
            return

        renamer = Renamer()
        if not renamer.renamable(item) or pane.isBlank:
            return

        focused_path = Path(item.getFullpath())
        placeholder = focused_path.suffix

        exts = []
        for item in pane.items:
            name = item.getName()
            _, ext = os.path.splitext(name)
            if 0 < len(ext):
                exts.append(ext)
        exts = sorted(list(set(exts)))

        def _listup_exts(
            update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
        ) -> tuple:
            found = []
            for ext in exts:
                if ext.lower().startswith(update_info.text.lower()):
                    found.append(ext)
            return found, 0

        new_ext, mod = window.commandLine(
            title="NewExt",
            text=placeholder,
            selection=[1, len(placeholder)],
            candidate_handler=_listup_exts,
            return_modkey=True,
        )

        new_ext = stringify(new_ext)
        if len(new_ext) < 1:
            return

        new_name = focused_path.stem + new_ext

        def _func() -> None:
            renamer.execute(focused_path, new_name, mod == ckit.MODKEY_SHIFT)

        Kiritori.wrap(_func)

    Keybinder().bind(rename_ext, "S-N")

    def duplicate_with_new_stem() -> None:
        pane = CPane()

        src_path = Path(pane.focusedItemPath)
        if pane.hasSelection:
            if 1 < len(pane.selectedItems):
                Kiritori.log("Caneled. (Select nothing or just 1 item)")
                return
            src_path = Path(pane.selectedItemPaths[0])

        sel_end = len(src_path.stem)
        sel_start = src_path.stem.rfind("_")
        if sel_start < 0:
            sel_start = sel_end
        prompt = "NewStem"
        placeholder = src_path.stem
        result = stringify(
            window.commandLine(
                title=prompt,
                text=placeholder,
                candidate_handler=SuffixHandler(True).invoke(),
                selection=[sel_start, sel_end],
            )
        )

        if len(result) < 1:
            return

        if src_path.is_file():
            result = result + src_path.suffix
        new_path = src_path.with_name(result)

        if smart_check_path(new_path):
            Kiritori.log("Canceled. (Same item exists)")
            return

        def _copy_as(new_path: str) -> None:
            if src_path.is_dir():
                shutil.copytree(src_path, new_path)
            else:
                shutil.copy(src_path, new_path)

        window.subThreadCall(_copy_as, (new_path,))
        pane.refresh()
        pane.focusByName(new_path.name)

    Keybinder().bind(duplicate_with_new_stem, "S-D")

    def duplicate_with_new_extension() -> None:
        pane = CPane()

        src_path = Path(pane.focusedItemPath)
        if pane.hasSelection:
            if 1 < len(pane.selectedItems):
                Kiritori.log("Caneled. (Select nothing or just 1 item)")
                return
            src_path = Path(pane.selectedItemPaths[0])

        if src_path.is_dir():
            Kiritori.log("Caneled. (Dirctory has no extension)")
            return

        sel_start = len(src_path.stem) + 1
        sel_end = len(src_path.name)
        prompt = "NewName"
        result = stringify(
            window.commandLine(
                title=prompt,
                text=src_path.name,
                selection=[sel_start, sel_end],
            )
        )

        if len(result) < 1:
            return

        new_path = src_path.with_name(result)

        if smart_check_path(new_path):
            Kiritori.log("Canceled. (Same item exists)")
            return

        def _copy_as(new_path: str) -> None:
            shutil.copy(src_path, new_path)

        window.subThreadCall(_copy_as, (new_path,))
        pane.refresh()
        pane.focusByName(new_path.name)

    Keybinder().bind(duplicate_with_new_extension, "A-S-D")

    def smart_copy_to_dir(remove_origin: bool) -> None:
        prompt = "MoveTo" if remove_origin else "CopyTo"

        pane = CPane()

        items = []
        for item in pane.selectedItems:
            if remove_origin and not hasattr(item, "delete"):
                continue
            items.append(item)

        if len(items) < 1:
            return

        dests = []
        for item in pane.items:
            if item.isdir() and not item.selected():
                name = item.getName()
                if name not in dests:
                    dests.append(name)

        obs_name = "_obsolete"
        if obs_name not in dests:
            dests.append(obs_name)

        def _listup_dests(
            update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
        ) -> tuple:
            found = [
                dest
                for dest in dests
                if dest.lower().startswith(update_info.text.lower())
            ]
            return found, 0

        result, mod = window.commandLine(
            prompt,
            candidate_handler=_listup_dests,
            return_modkey=True,
        )

        result = stringify(result)
        if len(result) < 1:
            return

        dir_path = os.path.join(pane.currentPath, result)
        if not smart_check_path(dir_path):
            pane.mkdir(result)
        pane.copyToChild(result, items, remove_origin)
        if mod == ckit.MODKEY_SHIFT:
            pane.openPath(dir_path)
        else:
            pane.focusByName(result)

    Keybinder().bind(lambda: smart_copy_to_dir(True), "S-M")
    Keybinder().bind(lambda: smart_copy_to_dir(False), "S-C")

    def smart_mkdir() -> None:
        pane = CPane()
        ts = datetime.datetime.today().strftime("%Y%m%d")
        result, mod = window.commandLine(
            "DirName",
            text=ts,
            selection=[0, len(ts)],
            candidate_handler=name_candidate_handler(False),
            return_modkey=True,
        )

        dirname = stringify(result)
        if len(dirname) < 1:
            return
        pane.mkdir(dirname)
        if mod == ckit.MODKEY_SHIFT:
            pane.openChild(dirname)

    Keybinder().bind(smart_mkdir, "C-S-N")

    def touch_new_file() -> None:
        pane = CPane()
        if not hasattr(pane.fileList.getLister(), "touch"):
            return

        result, mod = window.commandLine(
            "NewStem",
            candidate_handler=name_candidate_handler(True),
            return_modkey=True,
        )

        stem = stringify(result)
        if len(stem) < 1:
            return

        if "." in stem:
            ext = ""
        else:
            exts = ["txt", "md", "css", "html"]

            def _listup_exts(
                update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
            ) -> tuple:
                found = [
                    ext
                    for ext in exts
                    if ext.lower().startswith(update_info.text.lower())
                ]
                return found, 0

            ext = window.commandLine(
                "Extension",
                text=exts[0],
                selection=[0, len(exts[0])],
                candidate_handler=_listup_exts,
                auto_complete=True,
            )

            if ext is None:
                return
            if len(ext) < 1:
                ext = exts[0]
            ext = "." + ext

        new_name = stem + ext
        new_path = os.path.join(pane.currentPath, new_name)
        if smart_check_path(new_path):
            Kiritori.log("'{}' already exists.".format(stem))
            return

        pane.touch(new_name)
        if mod == ckit.MODKEY_SHIFT:
            shell_exec(new_path)

    Keybinder().bind(touch_new_file, "T")

    class Rect(NamedTuple):
        left: int
        top: int
        right: int
        bottom: int

    def to_home_position(force: bool) -> None:
        hwnd = window.getHWND()
        wnd = pyauto.Window.fromHWND(hwnd)
        main_monitor_info = None
        for info in pyauto.Window.getMonitorInfo():
            if info[2] == 1:
                main_monitor_info = info
                break
        if not main_monitor_info:
            return

        rect = Rect(*wnd.getRect())
        main_monitor_rect = Rect(*main_monitor_info[1])
        out_of_main_monitor = (
            main_monitor_rect.right < rect.right
            or rect.left < main_monitor_rect.left
            or rect.top < main_monitor_rect.top
            or main_monitor_rect.bottom < rect.bottom
        )
        if force or out_of_main_monitor:
            if wnd.isMaximized():
                wnd.restore()
            left = (main_monitor_rect.right - main_monitor_rect.left) // 2
            wnd.setRect([left, 0, main_monitor_rect.right, main_monitor_rect.bottom])
            window.command_MoveSeparatorCenter(None)

    Keybinder().bind(lambda: to_home_position(True), "C-0")

    class sorter_UnderscoreFirst:
        def __init__(self, order: int = 1) -> None:
            self.order = order

        def __call__(self, items) -> None:
            def _sort_key(item) -> tuple:
                dir_upper_flag = not item.isdir() if self.order == 1 else item.isdir()
                name = item.getName()
                underscore_count = len(name) - len(name.lstrip("_"))
                lower_name = name.lower()
                return (
                    dir_upper_flag,
                    not name.startswith("."),
                    not name.startswith("_"),
                    (-1 * underscore_count),
                    lower_name,
                )

            items.sort(key=_sort_key, reverse=self.order == -1)

    def setup_sorter() -> None:
        if len(window.sorter_list) == 4:
            window.sorter_list = [
                (
                    "U : Underscore Order",
                    sorter_UnderscoreFirst(),
                    sorter_UnderscoreFirst(order=-1),
                ),
            ] + window.sorter_list

        sorter = window.sorter_list[0][1]
        LeftPane().setSorter(sorter)
        RightPane().setSorter(sorter)

    setup_sorter()

    def reload_config() -> None:
        window.configure()
        ts = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S.%f")
        window.setStatusMessage("Reloaded config.py | {}".format(ts), 2000)

    Keybinder().bind(reload_config, "C-R", "F5")

    def open_desktop_to_other() -> None:
        pane = CPane()
        other = CPane(False)
        if DESKTOP_PATH not in [pane.currentPath, other.currentPath]:
            other.openPath(DESKTOP_PATH)
        pane.focusOther()

    Keybinder().bind(open_desktop_to_other, "A-O")

    def starting_position(both_pane: bool = False) -> None:
        window.command_MoveSeparatorCenter(None)
        pane = CPane()
        if pane.currentPath != DESKTOP_PATH:
            pane.openPath(DESKTOP_PATH)
        if both_pane:
            window.command_ChdirInactivePaneToOther(None)
            LeftPane().activate()

    Keybinder().bind(lambda: starting_position(False), "0")
    Keybinder().bind(lambda: starting_position(True), "S-0")

    def safe_quit() -> None:
        if window.ini.getint("MISC", "confirm_quit"):
            result = cfiler_msgbox.popMessageBox(
                window,
                cfiler_msgbox.MessageBox.TYPE_YESNO,
                "Confirm",
                "Quit?",
            )
            if result != cfiler_msgbox.MessageBox.RESULT_YES:
                return

        left = LeftPane()
        right = RightPane()
        for pane in [left, right]:
            if not pane.currentPath.startswith("C:"):
                pane.openPath(DESKTOP_PATH)

        window.quit()

    Keybinder().bind(safe_quit, "C-Q", "A-F4")

    def open_doc() -> None:
        shell_exec("https://github.dev/crftwr/cfiler/blob/master/cfiler_mainwindow.py")

    Keybinder().bind(open_doc, "C-F1")

    def edit_config() -> None:
        config_dir = os.path.join(os.environ.get("APPDATA", ""), "CraftFiler")
        if not smart_check_path(config_dir):
            Kiritori.log("cannot find config dir: {}".format(config_dir))
            return
        dir_path = config_dir
        if (real_path := os.path.realpath(config_dir)) != config_dir:
            dir_path = os.path.dirname(real_path)

        result = open_vscode(dir_path)
        if not result:
            subprocess.run(["explorer.exe", dir_path])

    Keybinder().bind(edit_config, "C-E")

    class FileHashDiff:
        def __init__(self, max_mb: int):
            self.max_mb = max_mb

        @staticmethod
        def count_bytes(s: str) -> int:
            n = 0
            for c in s:
                if unicodedata.east_asian_width(c) in "FWA":
                    n += 2
                else:
                    n += 1
            return n

        def to_hash(self, path: str) -> str:
            mb = 1024 * 1024
            read_size = 1 * mb if self.max_mb * mb < os.path.getsize(path) else None
            with open(path, "rb") as f:
                digest = hashlib.md5(f.read(read_size)).hexdigest()
            return digest

        def progress(self, name: str) -> None:
            print("checking first {}MB of: {}".format(self.max_mb, name))

        def compare(self) -> None:
            pane = CPane()
            other_pane = CPane(False)
            with_selection = other_pane.hasSelection
            _, dirname = os.path.split(pane.currentPath)
            _, other_dirname = os.path.split(other_pane.currentPath)

            def _scan(job_item: ckit.JobItem) -> None:
                targets = []
                for item in pane.selectedOrAllItems:
                    pane.unSelectByName(item.getName())
                    if not item.isdir():
                        targets.append(item)

                if len(targets) < 1:
                    return

                Kiritori.log("comparing md5 hash")

                window.setProgressValue(None)

                table = {}
                exts = set()

                for file in targets:
                    if job_item.isCanceled():
                        return
                    path = file.getFullpath()
                    digest = self.to_hash(path)
                    _, name = os.path.split(path)
                    _, ext = os.path.splitext(name)
                    self.progress(dirname + os.sep + name)
                    table[digest] = table.get(digest, []) + [name]
                    exts.add(ext)

                def __files_to_compare() -> (
                    Union[Iterator[ItemDefaultProtocol], List[ItemDefaultProtocol]]
                ):
                    if with_selection:
                        sels = other_pane.selectedItems
                        other_pane.unSelectAll()
                        return sels
                    return other_pane.traverse(True)

                clones: Dict[str, List[str]] = {}

                for item in __files_to_compare():
                    if job_item.isCanceled():
                        return
                    path = item.getFullpath()
                    _, ext = os.path.splitext(path)
                    if ext not in exts:
                        continue
                    rel = os.path.relpath(path, other_pane.currentPath)
                    self.progress(other_dirname + os.sep + rel)
                    digest = self.to_hash(path)
                    if digest in table:
                        names = table[digest]
                        for name in names:
                            clones[name] = clones.get(name, []) + [rel]

                job_item.clones = clones

            def _finish(job_item: ckit.JobItem) -> None:
                window.clearProgress()
                if job_item.isCanceled():
                    Kiritori.log("Canceled.")
                    return

                def _show() -> None:
                    print("Finished.\n")
                    if not job_item.clones or len(job_item.clones) < 1:
                        print("(There was no clone)")
                        return

                    for name, clone_names in job_item.clones.items():
                        pane.selectByName(name)
                        other_pane.selectByNames(
                            [n for n in clone_names if os.sep not in n]
                        )

                        filler = " " * self.count_bytes(name)
                        for i, n in enumerate(clone_names):
                            if i == 0:
                                print(name, "==", n)
                            else:
                                print(filler, "==", n)

                Kiritori.wrap(_show)

            job = ckit.JobItem(_scan, _finish)
            window.taskEnqueue(job, create_new_queue=False)

    def diffinity() -> None:
        exe_path = os.path.expandvars(
            r"${USERPROFILE}\scoop\apps\diffinity\current\Diffinity.exe"
        )

        if not smart_check_path(exe_path):
            Kiritori.log("cannnot find diffinity.exe...")
            return

        pane = CPane()
        left_path = ""
        right_path = ""

        if (
            pane.hasSelection
            and len(pane.selectedItems) == 2
            and not CPane(False).hasSelection
        ):
            left_path, right_path = pane.selectedItemPaths
        else:
            left_pane = LeftPane()
            right_pane = RightPane()
            if len(left_pane.selectedItems) == 1 and len(right_pane.selectedItems) == 1:
                left_path = left_pane.selectedItemPaths[0]
                right_path = right_pane.selectedItemPaths[0]

        if not left_path or not right_path:
            Kiritori.log("Select 1 item for each pane to compare.")
            return

        shell_exec(exe_path, left_path, right_path)

    def from_other_names() -> None:
        pane = CPane()
        pane.unSelectAll()
        active_names = pane.names
        other = CPane(False)
        other_names = [item.getName() for item in other.selectedOrAllItems]
        for name in active_names:
            if name in other_names:
                pane.selectByName(name)

    def from_active_names() -> None:
        pane = CPane()
        active_names = [item.getName() for item in pane.selectedOrAllItems]
        other = CPane(False)
        other.unSelectAll()
        other_names = other.names
        for name in other_names:
            if name in active_names:
                other.selectByName(name)

    def invoke_regex_selector(case: bool) -> CallbackFunc:
        def _selector() -> None:
            result, mod = window.commandLine("Regexp", return_modkey=True)

            if result:
                Selector().stemMatches(result, case, mod == ckit.MODKEY_SHIFT)

        return _selector

    Keybinder().bind(invoke_regex_selector(True), "S-Colon")

    def select_same_name() -> None:
        pane = CPane()
        active_names = pane.selectedItemNames
        if len(active_names) < 1:
            active_names = [pane.focusedItem.getName()]
        other = CPane(False)
        other.unSelectAll()

        for name in other.names:
            if name in active_names:
                other.selectByName(name)

    def select_name_common() -> None:
        pane = CPane()
        pane.unSelectAll()
        active_names = pane.names
        other = CPane(False)
        other.unSelectAll()
        other_names = other.names

        for name in active_names:
            if name in other_names:
                pane.selectByName(name)
        for name in other_names:
            if name in active_names:
                other.selectByName(name)

    def select_name_unique() -> None:
        pane = CPane()
        pane.unSelectAll()
        active_names = pane.names
        other = CPane(False)
        other.unSelectAll()
        other_names = other.names

        for name in active_names:
            if name not in other_names:
                pane.selectByName(name)
        for name in other_names:
            if name not in active_names:
                other.selectByName(name)

    def select_stem_startswith() -> None:
        result, mod = window.commandLine(
            "StartsWith",
            return_modkey=True,
            candidate_handler=PrefixHandler().invoke(),
        )
        if result:
            Selector().stemStartsWith(result, mod == ckit.MODKEY_SHIFT)

    Keybinder().bind(select_stem_startswith, "Caret", "A-A")

    def select_stem_endswith() -> None:
        result, mod = window.commandLine(
            "EndsWith",
            return_modkey=True,
            text=NameSuffix.sep,
            candidate_handler=SuffixHandler().invoke(),
        )
        if result:
            Selector().stemEndsWith(result, mod == ckit.MODKEY_SHIFT)

    Keybinder().bind(select_stem_endswith, "S-4", "A-E")

    def select_stem_contains() -> None:
        result, mod = window.commandLine("Contains", return_modkey=True)
        if result:
            Selector().stemContains(result, mod == ckit.MODKEY_SHIFT)

    Keybinder().bind(select_stem_contains, "Colon")

    def select_byext() -> None:
        pane = CPane()
        exts = []
        for item in pane.selectedOrAllItems:
            ext = Path(item.getFullpath()).suffix
            if ext and ext not in exts:
                exts.append(ext)

        if len(exts) < 1:
            return

        exts.sort(key=lambda ext: ext.lower())

        cursor_pos = 0
        if 0 < len(focused := Path(pane.focusedItemPath).suffix):
            if focused in exts:
                cursor_pos = exts.index(focused)

        result, mod = invoke_listwindow("Select Extension", exts, cursor_pos)

        if result < 0:
            return

        Selector().byExtension(exts[result], mod == ckit.MODKEY_SHIFT)

    Keybinder().bind(select_byext, "S-X")

    class PseudoVoicing:
        voicables = "かきくけこさしすせそたちつてとはひふへほカキクケコサシスセソタチツテトハヒフヘホ"

        def __init__(self, s) -> None:
            self._formatted = s

        def _replace(self, s: str, offset: int) -> str:
            c = s[0]
            if c not in self.voicables:
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
        pane = CPane()
        renamer = Renamer()
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
        pane = CPane()

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

    Keybinder().bind(save_clipboard_image_as_file, "C-S-I")

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
            return "[FILTERING {}]".format(self.root)

    def hide_unselected() -> None:
        pane = CPane()
        if pane.hasSelection:
            names = pane.selectedItemNames
            window.subThreadCall(
                pane.fileList.setFilter, (PathMatchFilter(pane.currentPath, names),)
            )
            pane.refresh()
            pane.focus(0)
            pane.repaint(PaintOption.Focused)
            CPane().unSelectAll()

    def clear_filter() -> None:
        pane = CPane()
        window.subThreadCall(pane.fileList.setFilter, (filter_Default("*"),))
        pane.refresh()
        pane.repaint(PaintOption.Focused)

    Keybinder().bind(clear_filter, "Q")

    def make_junction() -> None:
        active_pane = CPane()
        if not active_pane.hasSelection:
            return

        other_pane = CPane(False)
        dest = other_pane.currentPath
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
        path = CPane().currentPath
        bookmarks = [p for p in window.bookmark.getItems()]
        if path in bookmarks:
            window.bookmark.remove(path)
            Kiritori.log("Unbookmarked: '{}'".format(path))
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
            "CleanTempFiles": remove_tempfiles,
            "RenamePhotoFile": rename_photo_file,
            "RenameLightroomPhoto": rename_lightroom_photo_from_dropbox,
            "ZipSelections": compress_files,
            "SetBookmarkAlias": set_bookmark_alias,
            "CleanupBookmarkAlias": cleanup_alias_for_unbookmarked,
            "BookmarkHere": bookmark_here,
            "DocxToTxt": docx_to_txt,
            "EjectCurrentDrive": eject_current_drive,
            "ConcPdfGo": concatenate_pdf,
            "MakeJunction": make_junction,
            "ResetHotkey": reset_hotkey,
            "UnzipSelections": extract_archives,
            "HideUnselectedItems": hide_unselected,
            "ClearFilter": clear_filter,
            "Diffinity": diffinity,
            "MakeInternetShortcut": lambda: make_internet_shortcut(
                ckit.getClipboardText().strip()
            ),
            "RenamePseudoVoicing": rename_pseudo_voicing,
            "FindSameFile": FileHashDiff(2).compare,
            "FromOtherNames": from_other_names,
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

    def open_original(_) -> None:
        pane = window.main_window.activePane()
        visible = isinstance(pane.file_list.getLister(), lister_Default)
        path = Path(window.item.getFullpath())
        window.command_Close(None)
        pane.history.append(str(path.parent), path.name, visible, True)
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
        pane = window.main_window.activePane()
        name = pane.file_list.getItem(pane.cursor).getName()
        cfiler_msgbox.popMessageBox(
            window,
            cfiler_msgbox.MessageBox.TYPE_OK,
            "Copied:",
            name,
        )

    window.keymap["C-C"] = copy_content
    window.keymap["C-Insert"] = copy_content

    def copy_line_at_top(_) -> None:
        if window.binary:
            return
        c = get_content()
        if len(c) < 1:
            return
        line = c.splitlines()[window.scroll_info.pos]
        ckit.setClipboardText(line)
        cfiler_msgbox.popMessageBox(
            window,
            cfiler_msgbox.MessageBox.TYPE_OK,
            "Copied:",
            f"Line {window.scroll_info.pos + 1}",
        )

    window.keymap["C-T"] = copy_line_at_top

    def copy_displayed_lines(_) -> None:
        if window.binary:
            return
        c = get_content()
        if len(c) < 1:
            return
        lines = c.splitlines()
        top = window.scroll_info.pos
        bottom = min(top + window.height() - 1, top + window._numLines() - 1)
        s = "\n".join(lines[top:bottom])
        ckit.setClipboardText(s)
        cfiler_msgbox.popMessageBox(
            window,
            cfiler_msgbox.MessageBox.TYPE_OK,
            "Copied:",
            f"Lines {top + 1} - {min(len(lines), top + window.height() - 1)}",
        )

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

    def copy_path_to_clioboard(_) -> None:
        item = window.items[window.cursor]
        path = item.getFullpath()
        ckit.setClipboardText(path)
        window.setTitle(
            "{} - [ {} ] path copied!".format(
                cfiler_resource.cfiler_appname, window.items[window.cursor].name
            )
        )

    window.keymap["C-S-C"] = copy_path_to_clioboard

    def copy_image_to_clioboard(_) -> None:
        def _copy(_) -> None:
            item = window.items[window.cursor]
            path = item.getFullpath()
            cmd = (
                "PowerShell -NoProfile -Command "
                "Add-Type -AssemblyName System.Windows.Forms;"
                "[Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile('{}'));".format(
                    path
                )
            )
            subprocess.run(cmd, creationflags=subprocess.CREATE_NO_WINDOW, shell=True)

        def _finished(_) -> None:
            window.setTitle(
                "{} - [ {} ] copied!".format(
                    cfiler_resource.cfiler_appname, window.items[window.cursor].name
                )
            )

        job = ckit.JobItem(_copy, _finished)
        window.job_queue.enqueue(job)

    window.keymap["C-C"] = copy_image_to_clioboard
