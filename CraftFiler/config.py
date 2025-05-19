import configparser
import datetime
import hashlib
import inspect
import os
import re
import shutil
import subprocess
import time
import unicodedata
import urllib
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

# https://github.com/crftwr/cfiler/blob/master/cfiler_resource.py
import cfiler_resource

import cfiler_msgbox


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


def delay(msec: int = 50) -> None:
    time.sleep(msec / 1000)


def stringify(x: Union[str, None], trim: bool = True) -> str:
    if x:
        if trim:
            return x.strip()
        return x
    return ""


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


DESKTOP_PATH = os.path.expandvars(r"${USERPROFILE}\Desktop")


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
            str_size = "\ud83d\udcc1"
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

    def set_custom_theme():
        custom_theme = {
            "bg": (18, 37, 48),
            "fg": (255, 255, 255),
            "cursor0": (255, 255, 255),
            "cursor1": (255, 64, 64),
            "bar_fg": (0, 0, 0),
            "bar_error_fg": (200, 0, 0),
            "file_fg": (230, 230, 230),
            "dir_fg": (244, 215, 26),
            "hidden_file_fg": (85, 85, 85),
            "hidden_dir_fg": (85, 85, 50),
            "error_file_fg": (255, 0, 0),
            "select_file_bg1": (30, 100, 150),
            "select_file_bg2": (30, 100, 150),
            "bookmark_file_bg1": (107, 58, 112),
            "bookmark_file_bg2": (107, 58, 112),
            "file_cursor": (127, 255, 187),
            "select_bg": (30, 100, 150),
            "select_fg": (255, 255, 255),
            "choice_bg": (50, 50, 50),
            "choice_fg": (255, 255, 255),
            "diff_bg1": (100, 50, 50),
            "diff_bg2": (50, 100, 50),
            "diff_bg3": (50, 50, 100),
        }

        name = "black"
        ckit.ckit_theme.theme_name = name
        window.ini.set("THEME", "name", name)

        for k, v in custom_theme.items():
            ckit.ckit_theme.ini.set("COLOR", k, str(v))

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

    class Keybinder:

        @staticmethod
        def wrap(func: Callable) -> Callable:
            if inspect.signature(func).parameters.items():

                def _callback_with_arg(cmd_info: ckit.ckit_command.CommandInfo) -> None:
                    func(cmd_info)

                return _callback_with_arg

            def _callback(_) -> None:
                func()

            return _callback

        @classmethod
        def bind(
            cls,
            func: Callable,
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
            "C-A-N": window.command_DuplicateCfiler,
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

        def __init__(self, window: MainWindow, active: bool = True) -> None:
            self._window = window
            self._active = active
            if self._active:
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

        def setSorter(self, sorter: Callable) -> None:
            self._window.subThreadCall(self.fileList.setSorter, (sorter,))
            self.refresh()

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

        @property
        def width(self) -> int:
            left_width = self._window.left_window_width
            left_focused = self._window.focus == MainWindow.FOCUS_LEFT
            if (left_focused and self._active) or (
                not left_focused and not self._active
            ):
                return left_width
            return self._window.width() - left_width

        def focusOther(self, adjust: bool = True) -> None:
            if adjust:
                if self._window.width() - self.width < self.min_width:
                    self._window.command_MoveSeparatorCenter(None)
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
            if self.currentPath == path:
                return
            target = Path(path)
            if not smart_check_path(target, 2.0):
                Kiritori.log("invalid path: '{}'".format(path))
                return
            if target.is_file():
                path = str(target.parent)
                focus_name = target.name
            else:
                if focus_name is None:
                    for hist in self.entity.history.items:
                        if (d := hist[0]).startswith(path):
                            if d == path:
                                focus_name = hist[1]
                            else:
                                focus_name = d[len(path) + 1 :].split(os.sep)[0]
                            break
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

    def smart_cursorUp() -> None:
        pane = CPane(window)
        if pane.isBlank or pane.count == 1:
            return
        if pane.cursor == 0:
            pane.entity.cursor = pane.count - 1
        else:
            pane.entity.cursor -= 1
        pane.scrollToCursor()

    Keybinder().bind(smart_cursorUp, "K", "Up")

    def smart_cursorDown() -> None:
        pane = CPane(window)
        if pane.isBlank or pane.count == 1:
            return
        if pane.cursor == pane.count - 1:
            pane.entity.cursor = 0
        else:
            pane.entity.cursor += 1
        pane.scrollToCursor()

    Keybinder().bind(smart_cursorDown, "J", "Down")

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

    Keybinder().bind(toggle_pane_width, "C-S")

    Keybinder().bind(lambda: CPane(window).focusOther(), "C-L")

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

    def is_extractable(ext: str) -> bool:
        for archiver in window.archiver_list:
            for pattern in archiver[0].split():
                if ext == pattern[1:]:
                    return True
        return False

    def hook_enter() -> bool:
        # returning `True` hooks (skips) default action.

        pane = CPane(window)
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
            menu = ["Peek", "Extract"]
            result, _ = invoke_listwindow(window, "Archived file:", menu)
            if result == 0:
                window.command_InfoArchive(None)
            elif result == 1:
                if not pane.hasSelection:
                    pane.select(pane.cursor)
                smart_extract()
            return True

        if ext[1:].lower() in [
            "webp",
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

    Keybinder().bind(window.command_Enter, "L", "Right")

    def toggle_hidden() -> None:
        window.showHiddenFile(not window.isHiddenFileVisible())

    Keybinder().bind(toggle_hidden, "C-S-H")

    class LocalApps:
        def __init__(self, app_dict: dict) -> None:
            d = {}
            for name, path in app_dict.items():
                if smart_check_path(path):
                    d[name] = path
            self._dict = d

        @property
        def names(self) -> list:
            return list(self._dict.keys())

        def get_path(self, name: str) -> str:
            return self._dict.get(name, "")

    PDF_VIEWERS = {
        "sumatra": r"C:\Program Files\SumatraPDF\SumatraPDF.exe",
        "adobe": r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe",
        "xchange editor": r"C:\Program Files\Tracker Software\PDF Editor\PDFXEdit.exe",
    }

    TEXT_EDITORS = {
        "notepad": r"C:\Windows\System32\notepad.exe",
        "mery": os.path.expandvars(r"${LOCALAPPDATA}\Programs\Mery\Mery.exe"),
        "vscode": os.path.expandvars(
            r"${USERPROFILE}\scoop\apps\vscode\current\Code.exe"
        ),
    }

    def open_with() -> None:
        pane = CPane(window)
        if pane.isBlank or pane.focusedItem.isdir():
            return

        paths = pane.selectedItemPaths
        if len(paths) < 1:
            paths.append(pane.focusedItemPath)

        with_pdf_viewer = True
        for path in paths:
            if not path.endswith(".pdf"):
                with_pdf_viewer = False

        d = PDF_VIEWERS if with_pdf_viewer else TEXT_EDITORS
        apps = LocalApps(d)

        if not with_pdf_viewer and 1 < len(paths):
            return

        names = apps.names
        if len(names) < 1:
            return

        result = 0
        if 1 < len(names):
            result, _ = invoke_listwindow(window, "open with:", names)
            if result < 0:
                return

        exe_path = apps.get_path(names[result])
        for path in paths:
            shell_exec(exe_path, path)

    Keybinder().bind(open_with, "C-O")

    def quick_move() -> None:
        if not CPane(window).hasSelection:
            window.command_Select(None)
        window.command_Move(None)

    Keybinder().bind(quick_move, "M")

    def quick_copy() -> None:
        if not CPane(window).hasSelection:
            window.command_Select(None)
        window.command_Copy(None)

    Keybinder().bind(quick_copy, "C")

    def swap_pane() -> None:
        active = CPane(window, True)
        active_selects = active.selectedItemNames
        active_path = active.currentPath
        active_focus_name = None if active.isBlank else active.focusedItem.getName()
        active_sorter = active.fileList.getSorter()

        inactive = CPane(window, False)
        inactive_selects = inactive.selectedItemNames
        inactive_path = inactive.currentPath
        inactive_sorter = inactive.fileList.getSorter()

        inactive_focus_name = (
            None if inactive.isBlank else inactive.focusedItem.getName()
        )

        active.openPath(inactive_path, inactive_focus_name)
        active.selectByNames(inactive_selects)
        active.setSorter(inactive_sorter)

        inactive.openPath(active_path, active_focus_name)
        inactive.selectByNames(active_selects)
        inactive.setSorter(active_sorter)

        LeftPane(window).activate()

    Keybinder().bind(swap_pane, "S")

    def check_fzf() -> bool:
        return shutil.which("fzf.exe") is not None

    class BookmarkAlias:
        ini_section = "BOOKMARK_ALIAS"

        def __init__(self, window: MainWindow) -> None:
            self._window = window
            try:
                self._window.ini.add_section(self.ini_section)
            except configparser.DuplicateSectionError:
                pass

        def register(self, name: str, path: str) -> None:
            self._window.ini.set(self.ini_section, name, path)

        @staticmethod
        def to_leaf(path: str) -> str:
            path = path.rstrip(os.sep)
            p = Path(path)
            if 0 < len(p.name):
                return p.name
            return path.split(os.sep)[-1]

        def to_dict(self) -> dict:
            d = {}
            for opt in self._window.ini.items(self.ini_section):
                name = "{}[{}]".format(opt[0], self.to_leaf(opt[1]))
                d[name] = opt[1]
            paths_with_alias = d.values()
            for path in self._window.bookmark.getItems():
                if path not in paths_with_alias:
                    name = self.to_leaf(path)
                    d[name] = path
            return d

    class FuzzyBookmark:

        def __init__(self, window: MainWindow) -> None:
            self._table = BookmarkAlias(window).to_dict()

        def fzf(self) -> str:
            table = self._table
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

        alias = stringify(window.commandLine("Bookmark alias"))
        if len(alias) < 1:
            return

        BookmarkAlias(window).register(alias, target)

        if target not in window.bookmark.getItems():
            window.bookmark.append(target)
            if target != pane.currentPath:
                pane.refresh()
        Kiritori.log("Registered '{}' as alias for '{}'".format(alias, target))

    def read_docx(path: str) -> str:
        exe_path = os.path.expandvars(r"${USERPROFILE}\Personal\tools\bin\docxr.exe")
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
                    return f.read_text("utf-8").strip()
            return ""

        def filter_src(self) -> List[str]:
            existing = [
                d.name.lstrip("0123456789") for d in Path(self._current_path).iterdir()
            ]
            lines = []
            for s in self.read_src().splitlines():
                if not s.lstrip("#").split("|")[0] in existing:
                    lines.append(s)

            def _sort_key(line) -> Tuple[int]:
                return (len(line), line)

            return sorted(lines, key=_sort_key)

        def fzf(self) -> str:
            src = self.read_src()
            if len(src) < 1:
                Kiritori.log("src file '{}' not found...".format(self._src_name))
                return ""
            src = "\n".join(self.filter_src())
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

    Keybinder().bind(ruled_mkdir, "S-A-N")

    class zyl:
        def __init__(self) -> None:
            self._exe_path = os.path.expandvars(
                r"${USERPROFILE}\Personal\tools\bin\zyl.exe"
            )
            self._src_path = os.path.expandvars(r"${USERPROFILE}\Personal\launch.yaml")
            self._cmd = [
                self._exe_path,
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

    Keybinder().bind(zyl().invoke(), "C-Space")
    Keybinder().bind(zyl().invoke(True), "C-S-Space")

    class zyw:
        def __init__(self) -> None:
            self._exe_path = os.path.expandvars(
                r"${USERPROFILE}\Personal\tools\bin\zyw.exe"
            )
            self._cmd = [
                self._exe_path,
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
                    Keybinder().bind(self.invoke(search_all, offset), alt + shift + key)

    zyw().apply("Z")
    Keybinder().bind(zyw().invoke(False, 0), "S-F")
    Keybinder().bind(zyw().invoke(True, 0), "C-F")

    def concatenate_pdf() -> None:
        exe_path = os.path.expandvars(
            r"${USERPROFILE}\Personal\tools\bin\go-pdfconc.exe"
        )
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
        basename = stringify(
            window.commandLine(
                title="Outname", text=basename, selection=[0, len(basename)]
            )
        )
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
        print("Making shortcut for:\n{}".format(url))
        lines = ["[InternetShortcut]"]
        domain = urllib.parse.urlparse(url).netloc
        name = stringify(
            window.commandLine(
                "Shortcut title", text=" - {}".format(domain), selection=[0, 0]
            )
        )
        if len(name) < 1:
            print("Canceled.\n")
            return
        lines.append("URL={}".format(url))
        if not name.endswith(".url"):
            name = name + ".url"
        Path(CPane(window).currentPath, name).write_text(
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

    Keybinder().bind(on_paste, "C-V")

    class DriveHandler:
        wrapper = "<>"

        def __init__(self, window: MainWindow) -> None:
            pane = CPane(window)
            self._current_drive = Path(pane.currentPath).drive

        def listup(self, include_current: bool = False) -> List[str]:
            drives = []
            for d in ckit.getDrives():
                d += ":"
                if d == self._current_drive and not include_current:
                    continue
                detail = ckit.getDriveDisplayName(d)
                drives.append(
                    d
                    + self.wrapper[0]
                    + detail[: detail.find("(") - 1]
                    + self.wrapper[-1]
                )
            return drives

        def parse(self, s: str) -> str:
            if self.wrapper[0] in s:
                return s[: s.find(self.wrapper[0])]
            return s

    def smart_jump_input() -> None:
        pane = CPane(window)

        drive_handler = DriveHandler(window)
        drives = drive_handler.listup()

        def _listup_names(update_info: ckit.ckit_widget.EditWidget.UpdateInfo) -> tuple:
            found = []
            for name in drives + pane.names:
                if name.lower().startswith(update_info.text.lower()):
                    found.append(name)
            return found, 0

        result = stringify(
            window.commandLine(
                title="JumpInputSmart",
                auto_complete=True,
                candidate_handler=_listup_names,
            )
        )
        result = drive_handler.parse(result)
        if len(result) < 1:
            return
        if ":" in result:
            if result == "C:":
                pane.openPath(DESKTOP_PATH)
                return
            pane.openPath(result)
        else:
            pane.openPath(os.path.join(pane.currentPath, result))

    Keybinder().bind(smart_jump_input, "F")

    def eject_current_drive() -> None:
        pane = CPane(window)
        current = pane.currentPath
        if current.startswith("C:"):
            return

        current_drive = Path(current).drive
        pane.openPath(DESKTOP_PATH)

        def _eject(job_item: ckit.JobItem) -> None:
            job_item.result = None
            cmd = (
                "PowerShell -Command "
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

    def smart_extract() -> None:
        active_pane = CPane(window)

        for item in active_pane.selectedItems:
            ext = Path(item.getFullpath()).suffix
            if not is_extractable(ext):
                active_pane.unSelectByName(item.getName())

        if not active_pane.hasSelection:
            return

        placeholder = datetime.datetime.today().strftime("unzip_%Y%m%d%H%M%S")
        result = stringify(window.commandLine("Extract as", text=placeholder))
        if len(result) < 1:
            return

        if active_pane.byName(result) != -1:
            Kiritori.log("'{}' already exists.".format(result))
            return

        active_pane.mkdir(result, False)
        extract_path = os.path.join(active_pane.currentPath, result)

        inactive_pane = CPane(window, False)
        inactive_pane.openPath(extract_path)
        window.command_ExtractArchive(None)

    def recylcebin() -> None:
        shell_exec("shell:RecycleBinFolder")

    Keybinder().bind(recylcebin, "Delete")

    def copy_current_path() -> None:
        pane = CPane(window)
        p = pane.currentPath
        ckit.setClipboardText(p)
        window.setStatusMessage("copied current path: '{}'".format(p), 3000)

    Keybinder().bind(copy_current_path, "C-A-P")

    def on_copy() -> None:
        selection_left, selection_right = window.log_pane.selection
        if selection_left != selection_right:
            window.command_SetClipboard_LogSelected(None)
            return

        pane = CPane(window)

        targets = []
        if pane.isBlank:
            targets.append(pane.currentPath)
        else:
            for i in range(pane.count):
                item = pane.byIndex(i)
                if item.selected():
                    targets.append(item.getFullpath())
                if len(targets) < 1:
                    targets.append(pane.focusedItemPath)

        menu = ["Fullpath", "Name", "Basename"]
        result, _ = invoke_listwindow(window, "Copy", menu)
        if result < 0:
            return

        lines = []
        if result == 0:
            lines = targets
        elif result == 1:
            for p in targets:
                lines.append(Path(p).name)
        else:
            for p in targets:
                lines.append(Path(p).stem)

        count = len(lines)
        if 0 < count:
            ckit.setClipboardText("\n".join(lines))
            s = "Copied {} of {} item".format(menu[result], count)
            if 1 < count:
                s += "s."
            else:
                s += "."
            Kiritori.log(s)

    Keybinder().bind(on_copy, "C-C")

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
                Keybinder().bind(v, k)

    Selector(window).apply()

    def unselect_panes() -> None:
        CPane(window).unSelectAll()
        CPane(window, False).unSelectAll()

    Keybinder().bind(unselect_panes, "C-U")

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

    Keybinder().bind(smart_jumpDown(False), "C-J")
    Keybinder().bind(smart_jumpDown(False), "C-Down")
    Keybinder().bind(smart_jumpDown(True), "S-C-J")
    Keybinder().bind(smart_jumpDown(True), "S-C-Down")

    def smart_jumpUp(selecting: bool = False) -> None:
        def _jumper() -> None:
            SmartJumper(window).up(selecting)

        return _jumper

    Keybinder().bind(smart_jumpUp(False), "C-K")
    Keybinder().bind(smart_jumpUp(False), "C-Up")
    Keybinder().bind(smart_jumpUp(True), "S-C-K")
    Keybinder().bind(smart_jumpUp(True), "S-C-Up")

    def duplicate_pane() -> None:
        window.command_ChdirInactivePaneToOther(None)
        pane = CPane(window)
        pane.focusOther()

    Keybinder().bind(duplicate_pane, "W", "D")

    def open_on_explorer() -> None:
        pane = CPane(window, True)
        shell_exec(pane.currentPath)

    Keybinder().bind(open_on_explorer, "C-S-E")

    def open_to_other() -> None:
        active_pane = CPane(window, True)
        if not active_pane.isBlank:
            inactive_pane = CPane(window, False)
            inactive_pane.openPath(active_pane.focusedItemPath)
            active_pane.focusOther()

    Keybinder().bind(open_to_other, "S-L")

    def open_parent_to_other() -> None:
        active_pane = CPane(window, True)
        parent, current_name = os.path.split(active_pane.currentPath)
        inactive_pane = CPane(window, False)
        inactive_pane.openPath(parent, current_name)
        active_pane.focusOther()

    Keybinder().bind(open_parent_to_other, "S-U", "S-H")

    def on_vscode() -> None:
        vscode_path = TEXT_EDITORS["vscode"]
        if smart_check_path(vscode_path):
            pane = CPane(window)
            shell_exec(vscode_path, pane.currentPath)

    Keybinder().bind(on_vscode, "V")

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

    class RenameConfig:
        ini_section = "RENAME_CONFIG"

        def __init__(self, window: MainWindow, option_name: str) -> None:
            self._window = window
            try:
                self._window.ini.add_section(self.ini_section)
            except configparser.DuplicateSectionError:
                pass
            self._option_name = option_name

        def register(self, value: str) -> None:
            self._window.ini.set(self.ini_section, self._option_name, value)

        @property
        def value(self) -> str:
            try:
                return self._window.ini.get(self.ini_section, self._option_name)
            except:
                return ""

    class RenameInfo(NamedTuple):
        orgPath: Path
        newName: str

    def rename_substr() -> None:
        renamer = Renamer(window)

        targets = renamer.candidate
        if len(targets) < 1:
            return

        placeholder = ";-1"
        sel_end = 0

        rename_config_substr = RenameConfig(window, "substr")
        if 0 < len(last := rename_config_substr.value):
            placeholder = last
            sel_end = last.find(";")

        print("Rename substring (extract part of filename):")
        result = stringify(
            window.commandLine(
                "Offset[;Length]", text=placeholder, selection=[0, sel_end]
            )
        )

        if len(result) < 1:
            print("Canceled.\n")
            return

        sep = ";"
        if sep not in result:
            result += ";-1"
        else:
            if result.startswith(sep):
                result = "0" + result

        offset = int(result[: result.find(sep)])
        length = int(result[result.rfind(sep) + 1 :])

        if offset == 0 and length == -1:
            print("Canceled.\n")
            return

        rename_config_substr.register(result)

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
        renamer = Renamer(window)

        targets = renamer.candidate
        if len(targets) < 1:
            return

        placeholder = "@-1"
        sel_end = 0

        rename_config_insert = RenameConfig(window, "insert")
        last_insert = rename_config_insert.value
        if 0 < len(last_insert):
            placeholder = last_insert
            sel_end = last_insert.find("@")

        print("Rename insert:")
        result = stringify(
            window.commandLine(
                "Text[@position]", text=placeholder, selection=[0, sel_end]
            ),
            False,
        ).rstrip()

        if len(result) < 1:
            print("Canceled.\n")
            return

        sep = "@"
        if result.startswith(sep):
            print("Canceled.\n")
            return

        if sep not in result:
            result += "@-1"
        else:
            if result.endswith(sep):
                result += "-1"

        rename_config_insert.register(result)

        ins = result[: result.rfind(sep)]
        pos = int(result[result.rfind(sep) + 1 :])

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

    def rename_index() -> None:
        renamer = Renamer(window)

        targets = renamer.candidate
        if len(targets) < 1:
            return

        placeholder = "01@-1,1"
        rename_config_index = RenameConfig(window, "index")
        last_value = rename_config_index.value
        if 0 < len(last_value):
            placeholder = last_value

        print("Rename insert index:")
        result = stringify(
            window.commandLine(
                "Index[@position,step,skips1,skips2,...]",
                text=placeholder,
                selection=[0, 2],
            ),
            trim=False,
        )

        if len(result) < 1:
            print("Canceled.\n")
            return

        class NameIndex:
            position = -1
            step = 1
            skips = []

            def __init__(self, s: str) -> None:
                commands = s.split("@")
                self.index_template = commands[0].rstrip()
                if 1 < len(commands):
                    args = [a.strip() for a in commands[1].split(",")]
                    self.position = int(args[0])
                    if 1 < len(args):
                        self.step = int(args[1])
                    if 2 < len(args):
                        self.skips = [int(a) for a in args[2:]]

            @property
            def width(self) -> int:
                return len(self.index_template)

            @property
            def filler(self) -> str:
                c = self.index_template[0]
                if c in "123456789":
                    return ""
                return c

            @property
            def start(self) -> Union[int, None]:
                try:
                    return int(self.index_template.lstrip(self.filler))
                except:
                    return None

            def is_valid(self) -> bool:
                return self.start is not None

            def increment(self, i: int) -> int:
                i += self.step
                if len(self.skips) < 1:
                    return i
                while 1:
                    if i not in self.skips:
                        break
                    else:
                        i += self.step
                return i

        ni = NameIndex(result)
        if not ni.is_valid():
            print("Canceled (Invalid format).\n")
            return

        print(result)
        rename_config_index.register(result)

        def _confirm() -> Tuple[List[RenameInfo], bool]:
            infos = []
            lines = []
            idx = ni.start
            for item in targets:
                org_path = Path(item.getFullpath())
                org_stem = org_path.stem
                pos = ni.position
                if ni.position < 0:
                    pos = len(org_stem) + 1 + ni.position
                new_name = (
                    org_stem[:pos]
                    + str(idx).rjust(ni.width, ni.filler)
                    + org_stem[pos:]
                    + org_path.suffix
                )
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
        renamer = Renamer(window)

        targets = renamer.candidate
        if len(targets) < 1:
            return

        placeholder = "/"
        sel_end = 0

        rename_config_regexp = RenameConfig(window, "regexp")
        last_regexp = rename_config_regexp.value
        if 0 < len(last_regexp):
            placeholder = last_regexp
            sel_end = last_regexp.find("/")

        print("Rename with regexp-replace. Trailing `/c` enables case-sensitive-mode")
        result = window.commandLine(
            "[regexp]/[replace with](/c)", text=placeholder, selection=[0, sel_end]
        )

        if not result:
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
            def from_reg(self) -> re.Pattern:
                flag = re.IGNORECASE if self.args[2] == "" else re.NOFLAG
                return re.compile(self.args[0], flag)

            @property
            def to_str(self) -> str:
                return self.args[1]

        rc = RegCommand(result)
        if not rc.is_valid():
            print("Canceled (Invalid command).\n")
            return

        rename_config_regexp.register(result)
        reg = rc.from_reg

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

    class Prefixer:
        sep = "_"

        def __init__(self, window: MainWindow) -> None:
            pane = CPane(window)
            self.names = []
            for item in pane.selectedOrAllItems:
                name = item.getName()
                if self.sep not in name or name.startswith(self.sep):
                    continue
                p = Path(pane.currentPath, name)
                self.names.append(p.stem)

        @property
        def possible_prefix(self) -> List[str]:
            pres = []
            for name in self.names:
                for i, c in enumerate(name):
                    if c == self.sep:
                        pres.append(name[: i + 1])
            return sorted(list(set(pres)), key=len)

        def candidates(self, s: str) -> List[str]:
            pres = self.possible_prefix
            found = []
            for pre in pres:
                if pre.startswith(s):
                    found.append(pre)
            return found

        def __call__(
            self, update_info: ckit.ckit_widget.EditWidget.UpdateInfo
        ) -> Tuple[List[str], int]:
            return self.candidates(update_info.text), 0

    class Suffixer:
        sep = "_"

        def __init__(
            self,
            window: MainWindow,
            with_timestamp: bool = False,
            additional: List[str] = [],
        ) -> None:
            pane = CPane(window)
            self.timestamp = ""
            if with_timestamp:
                self.timestamp = datetime.datetime.today().strftime("%Y%m%d")
            self._additional = [self.sep + a for a in additional]
            self.names = []
            for item in pane.selectedOrAllItems:
                name = item.getName()
                if self.sep not in name or name.startswith(self.sep):
                    continue
                p = Path(pane.currentPath, name)
                self.names.append(p.stem)

        @property
        def possible_suffix(self) -> List[str]:
            sufs = []
            for name in self.names:
                for i, c in enumerate(name):
                    if c == self.sep:
                        sufs.append(name[i:])
            sufs = sorted(list(set(sufs)), key=len)
            if 0 < len(self._additional):
                sufs = self._additional + sufs
            if self.timestamp:
                if (s := self.sep + self.timestamp) not in sufs:
                    sufs = [s] + sufs
            return sufs

        def candidates(self, s: str) -> List[str]:
            sufs = self.possible_suffix
            if self.sep not in s:
                return [s + suf for suf in sufs]
            if s.endswith(self.sep):
                return [s + suf[1:] for suf in sufs]
            found = []
            sep_pos = s.find(self.sep)
            command_suffix = s[sep_pos:]
            for suf in sufs:
                if suf.startswith(command_suffix):
                    found.append(s[:sep_pos] + suf)
            return found

        def __call__(
            self, update_info: ckit.ckit_widget.EditWidget.UpdateInfo
        ) -> Tuple[List[str], int]:
            return self.candidates(update_info.text), 0

    def invoke_renamer() -> None:
        pane = CPane(window)
        item = pane.focusedItem

        renamer = Renamer(window)
        if not renamer.renamable(item) or pane.isBlank:
            return

        org_path = Path(item.getFullpath())
        offset = len(org_path.stem)

        ts = item.time()
        item_timestamp = "{}{:02}{:02}".format(ts[0], ts[1], ts[2])
        additional_suffix = [item_timestamp]

        if mo := re.search(r"\d{8}", pane.currentPath):
            ts = mo.group(0)
            if ts != additional_suffix[0]:
                additional_suffix.append(ts)

        placeholder = org_path.stem
        sel = [offset, offset]

        other_pane = CPane(window, False)
        for p in [pane, other_pane]:
            if p.hasSelection and len(p.selectedItems) == 1:
                new_stem = Path(p.selectedItemPaths[0]).stem
                if new_stem != placeholder:
                    placeholder = placeholder + new_stem
                    sel[0] = 0
                    break

        new_stem, mod = window.commandLine(
            title="NewStem",
            text=placeholder,
            selection=sel,
            candidate_handler=Suffixer(window, True, additional_suffix),
            return_modkey=True,
        )

        new_stem = stringify(new_stem)
        if len(new_stem) < 1:
            return

        new_name = new_stem + org_path.suffix

        def _func() -> None:
            renamer.execute(org_path, new_name, mod == ckit.MODKEY_SHIFT)

        Kiritori.wrap(_func)

    Keybinder().bind(invoke_renamer, "N")

    def duplicate_file() -> None:
        pane = CPane(window)

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
                candidate_handler=Suffixer(window, True),
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
            if Path(src_path).is_dir():
                shutil.copytree(src_path, new_path)
            else:
                shutil.copy(src_path, new_path)

        window.subThreadCall(_copy_as, (new_path,))
        pane.refresh()
        pane.focusByName(Path(new_path).name)

    Keybinder().bind(duplicate_file, "S-D")

    def smart_copy_to_dir(remove_origin: bool) -> None:
        prompt = "MoveTo" if remove_origin else "CopyTo"

        pane = CPane(window)

        items = []
        for item in pane.selectedItems:
            if remove_origin and not hasattr(item, "delete"):
                continue
            items.append(item)

        if len(items) < 1:
            return

        default_name = "_obsolete"

        def _listup_dests(
            update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
        ) -> tuple:
            found = []
            if default_name not in pane.names:
                found.append(default_name)
            for item in pane.items:
                if item.isdir() and not item.selected():
                    name = item.getName()
                    if name.startswith(update_info.text):
                        found.append(name)
            return found, 0

        result, mod = window.commandLine(
            prompt,
            text=default_name,
            selection=[0, len(default_name)],
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
        pane = CPane(window)
        ts = datetime.datetime.today().strftime("%Y%m%d")
        result, mod = window.commandLine(
            "DirName",
            text=ts,
            selection=[0, len(ts)],
            candidate_handler=Suffixer(window, False),
            return_modkey=True,
        )

        dirname = stringify(result)
        if len(dirname) < 1:
            return
        pane.mkdir(dirname)
        if mod == ckit.MODKEY_SHIFT:
            pane.openChild(dirname)

    Keybinder().bind(smart_mkdir, "C-S-N")

    class Toucher:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

        def invoke(self, extension: str = "") -> None:
            def _func() -> None:
                pane = CPane(self._window)
                if not hasattr(pane.fileList.getLister(), "touch"):
                    return

                prompt = "NewFileName"
                ext = "." + extension if 0 < len(extension) else ""
                if ext:
                    prompt += " ({})".format(ext)
                else:
                    prompt += " (with extension)"

                placeholder = ""
                sel = [0, 0]

                other_pane = CPane(self._window, False)
                for p in [pane, other_pane]:
                    if p.hasSelection and len(p.selectedItems) == 1:
                        placeholder = Path(p.selectedItemPaths[0]).stem
                        sel[1] = len(placeholder)
                        break

                result, mod = window.commandLine(
                    prompt,
                    text=placeholder,
                    selection=sel,
                    candidate_handler=Suffixer(window, True),
                    return_modkey=True,
                )

                filename = stringify(result)
                if len(filename) < 1:
                    return

                if ext and not filename.endswith(ext):
                    filename += ext
                new_path = os.path.join(pane.currentPath, filename)
                if smart_check_path(new_path):
                    Kiritori.log("'{}' already exists.".format(filename))
                    return
                pane.touch(filename)
                if mod == ckit.MODKEY_SHIFT:
                    shell_exec(new_path)

            return _func

    TOUCHER = Toucher(window)

    Keybinder().bind(TOUCHER.invoke("txt"), "T")
    Keybinder().bind(TOUCHER.invoke("md"), "A-T")
    Keybinder().bind(TOUCHER.invoke(""), "C-N")

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

    Keybinder().bind(lambda: to_home_position(True), "C-0")

    class sorter_UnderscoreFirst:
        def __init__(self, order: int = 1) -> None:
            self.order = order

        def __call__(self, items) -> None:
            def _sort_key(item) -> tuple:
                dir_upper_flag = not item.isdir() if self.order == 1 else item.isdir()
                starts_with_underscore = item.name.startswith("_")
                underscore_count = len(item.name) - len(item.name.lstrip("_"))
                lower_name = item.name.lower()
                return (
                    dir_upper_flag,
                    not starts_with_underscore,
                    underscore_count,
                    lower_name,
                )

            items.sort(key=_sort_key, reverse=self.order == -1)

    class SorterHandler:
        def __init__(self, window: MainWindow) -> None:
            if len(window.sorter_list) == 4:
                window.sorter_list = [
                    (
                        "U : Underscore First",
                        sorter_UnderscoreFirst(),
                        sorter_UnderscoreFirst(order=-1),
                    ),
                ] + window.sorter_list
            self._window = window

        def apply(self) -> None:
            name = None
            if focus := CPane(self._window).focusedItem:
                name = focus.getName()

            sorter = self._window.sorter_list[0][1]
            LeftPane(self._window).setSorter(sorter)
            RightPane(self._window).setSorter(sorter)

            if name:
                CPane(window).focusByName(name)

    SorterHandler(window).apply()

    def reload_config() -> None:
        window.configure()
        to_home_position(False)
        ts = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S.%f")
        window.setStatusMessage("reloaded config.py | {}".format(ts), 2000)

    Keybinder().bind(reload_config, "C-R", "F5")

    def open_desktop_to_other() -> None:
        pane = CPane(window)
        other = CPane(window, False)
        if DESKTOP_PATH not in [pane.currentPath, other.currentPath]:
            other.openPath(DESKTOP_PATH)
        else:
            pane.focusOther()

    Keybinder().bind(open_desktop_to_other, "A-O")

    def starting_position(both_pane: bool = False) -> None:
        window.command_MoveSeparatorCenter(None)
        pane = CPane(window, True)
        if pane.currentPath != DESKTOP_PATH:
            pane.openPath(DESKTOP_PATH)
        if both_pane:
            window.command_ChdirInactivePaneToOther(None)
            LeftPane(window).activate()

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

        left = LeftPane(window)
        right = RightPane(window)
        for pane in [left, right]:
            if not pane.currentPath.startswith("C:"):
                pane.openPath(DESKTOP_PATH)

        window.quit()

    Keybinder().bind(safe_quit, "C-Q", "A-F4")

    def open_doc() -> None:
        help_path = os.path.join(ckit.getAppExePath(), "doc", "index.html")
        shell_exec(help_path)

    Keybinder().bind(open_doc, "C-F1")

    def edit_config() -> None:
        config_dir = os.path.join(os.environ.get("APPDATA"), "CraftFiler")
        if not smart_check_path(config_dir):
            Kiritori.log("cannot find config dir: {}".format(config_dir))
            return
        dir_path = config_dir
        if (real_path := os.path.realpath(config_dir)) != config_dir:
            dir_path = os.path.dirname(real_path)
        vscode_path = TEXT_EDITORS["vscode"]
        if smart_check_path(vscode_path):
            shell_exec(vscode_path, dir_path)
        else:
            shell_exec(dir_path)

    Keybinder().bind(edit_config, "C-E")

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
        exe_path = os.path.expandvars(
            r"${USERPROFILE}\scoop\apps\diffinity\current\Diffinity.exe"
        )
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

    Keybinder().bind(invoke_regex_selector(True), "S-Colon")

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
        result, mod = window.commandLine(
            "StartsWith",
            return_modkey=True,
            candidate_handler=Prefixer(window),
        )
        if result:
            Selector(window).stemStartsWith(result, mod == ckit.MODKEY_SHIFT)

    Keybinder().bind(select_stem_startswith, "Caret")

    def select_stem_endswith() -> None:
        result, mod = window.commandLine(
            "EndsWith",
            return_modkey=True,
            text=Suffixer.sep,
            candidate_handler=Suffixer(window),
        )
        if result:
            Selector(window).stemEndsWith(result, mod == ckit.MODKEY_SHIFT)

    Keybinder().bind(select_stem_endswith, "S-4")

    def select_stem_contains() -> None:
        result, mod = window.commandLine("Contains", return_modkey=True)
        if result:
            Selector(window).stemContains(result, mod == ckit.MODKEY_SHIFT)

    Keybinder().bind(select_stem_contains, "Colon")

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

    Keybinder().bind(select_byext, "S-X")

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
        pane = CPane(window)
        if pane.hasSelection:
            names = pane.selectedItemNames
            window.subThreadCall(
                pane.fileList.setFilter, (PathMatchFilter(pane.currentPath, names),)
            )
            pane.refresh()
            pane.focus(0)
            pane.repaint(PO.Focused)
            CPane(window).unSelectAll()

    def clear_filter() -> None:
        pane = CPane(window)
        window.subThreadCall(pane.fileList.setFilter, (filter_Default("*"),))
        pane.refresh()
        pane.repaint(PO.Focused)

    Keybinder().bind(clear_filter, "Q")

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
            "SetBookmarkAlias": set_bookmark_alias,
            "CleanupBookmarkAlias": cleanup_alias_for_unbookmarked,
            "BookmarkHere": bookmark_here,
            "DocxToTxt": docx_to_txt,
            "EjectCurrentDrive": eject_current_drive,
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
        window.setTitle(
            "{} - [ {} ] copied line {}.".format(
                cfiler_resource.cfiler_appname,
                window.item.name,
                window.scroll_info.pos + 1,
            )
        )

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
            cmd = (
                "PowerShell -Command "
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
