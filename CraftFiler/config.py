import datetime
import hashlib
import inspect
import os
import re
import shutil
import subprocess
import time
import unicodedata

from collections import namedtuple
from pathlib import Path
from typing import List, Tuple, Callable, Union

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

from cfiler_misc import candidate_Filename


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
USER_PROFILE = os.environ.get("USERPROFILE") or ""
LINE_BREAK = os.linesep


def delay(msec: int = 50) -> None:
    time.sleep(msec / 1000)


def configure(window: MainWindow) -> None:

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
            if key in self._data:
                if type(value) is tuple:
                    self._data[key] = value
                else:
                    colorcode = value.strip("#")
                    if len(colorcode) == 6:
                        r, g, b = colorcode[:2], colorcode[2:4], colorcode[4:6]
                        self._data[key] = (int(r, 16), int(g, 16), int(b, 16))

        def to_string(self) -> str:
            lines = ["[COLOR]"]
            for key, value in self._data.items():
                line = "{} = {}".format(key, value)
                lines.append(line)
            return "\n".join(lines)

        def overwrite(self) -> None:
            theme = self.to_string()
            if not self._theme_path.exists() or self._theme_path.read_text() != theme:
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

    def print_log(s) -> None:
        sep = "-"
        ts = datetime.datetime.today().strftime(
            " %Y-%m-%d %H:%M:%S.%f {}".format(sep * 2)
        )
        ww = window.width()
        print("\n{}".format(ts.rjust(ww, sep)))
        print(s)
        print("{}\n".format(sep * ww))

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
            "C-L": window.command_FocusOther,
            "C-Right": window.command_FocusOther,
            "O": window.command_ChdirActivePaneToOther,
            "S-O": window.command_ChdirInactivePaneToOther,
            "A": window.command_CursorTop,
            "E": window.command_CursorBottom,
            "Home": window.command_CursorTop,
            "End": window.command_CursorBottom,
            "C-S-P": window.command_CommandLine,
            "C-S-N": window.command_Mkdir,
            "H": window.command_GotoParentDir,
            "Left": window.command_GotoParentDir,
            "S-F10": window.command_ContextMenu,
            "A-S-F10": window.command_ContextMenuDir,
            "C-A-N": window.command_DuplicateCfiler,
            "C-Up": window.command_CursorUpSelectedOrBookmark,
            "C-K": window.command_CursorUpSelectedOrBookmark,
            "C-Down": window.command_CursorDownSelectedOrBookmark,
            "C-J": window.command_CursorDownSelectedOrBookmark,
            "OpenBracket": window.command_MoveSeparatorLeft,
            "CloseBracket": window.command_MoveSeparatorRight,
            "Yen": window.command_MoveSeparatorCenter,
            "A-S": window.command_SetSorter,
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

        def bindmulti(self, mapping: dict) -> None:
            for key, func in mapping.items():
                self._window.keymap[key] = self.wrap(func)

    KEYBINDER = Keybinder(window)

    def invoke_listwindow(
        window: MainWindow, prompt: str, items, ini_pos: int = 0
    ) -> Tuple[str, int]:
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

    class JumpList:
        def __init__(self, window: MainWindow) -> None:
            self._window = window
            self._list_items = []
            self._menu_table = {}

        def register(self, name: str, path: str) -> None:
            p = Path(path)
            try:
                if p.exists():
                    self._menu_table[name] = path
                    self._list_items.append(ListItem(name, False))
            except Exception as e:
                print_log(e)

        @property
        def bookmarks(self) -> List[str]:
            bookmark = self._window.bookmark.getItems()
            return sorted(bookmark, key=lambda p: Path(p).name.lower())

        def to_menu_name(self, path: str) -> str:
            p = Path(path)
            names = [item.name for item in self._list_items]
            if p.name in names:
                return "{} ({})".format(p.name, p.parent)
            return p.name

        def register_bookmark(self) -> None:
            for path in self.bookmarks:
                if path not in self._menu_table.values():
                    name = self.to_menu_name(path)
                    self._menu_table[name] = path
                    item = ListItem(name, True)
                    self._list_items.append(item)

        def jump(self) -> None:
            for name, path in {
                "Desktop": str(Path(USER_PROFILE, "Desktop")),
                "Scan": r"X:\scan",
                "Dropbox": str(Path(USER_PROFILE, "Dropbox")),
                "Dropbox Share": str(
                    Path(USER_PROFILE, "Dropbox", "_sharing", "_yuhikaku")
                ),
            }.items():
                self.register(name, path)
            self.register_bookmark()

            result, mod = invoke_listwindow(self._window, "Jump", self._list_items)
            if -1 < result:
                item = self._list_items[result]
                dest = self._menu_table[item.name]
                active = CPane(self._window, True)
                other = CPane(self._window, False)
                if mod == ckit.MODKEY_SHIFT:
                    other.openPath(dest)
                else:
                    active.openPath(dest)

    KEYBINDER.bind("C-Space", lambda: JumpList(window).jump())

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

        @property
        def history(self) -> History:
            return self._pane.history

        def appendHistory(self, path: str) -> History:
            p = Path(path)
            lister = self.lister
            visible = isinstance(lister, lister_Default)
            return self._pane.history.append(str(p.parent), p.name, visible, False)

        @property
        def cursor(self) -> int:
            return self._pane.cursor

        def focus(self, i: int) -> None:
            if self.isBlank:
                return
            if i < 0 or self.count <= i:
                return
            self._pane.cursor = i
            self.scrollToCursor()

        def byName(self, name: str) -> int:
            return self.fileList.indexOf(name)

        def hasName(self, name: str) -> bool:
            return self.byName(name) != -1

        def focusByName(self, name: str) -> None:
            i = self.byName(name)
            if i < 0:
                return
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

        def unSelect(self, i: int) -> None:
            self.setSelectionState(i, False)

        def selectByName(self, name: str) -> None:
            i = self.byName(name)
            if i < 0:
                return
            self.select(i)
            self.applySelectionHighlight()

        def selectByNames(self, names: list) -> None:
            for name in names:
                self.selectByName(name)

        @property
        def selectionTop(self) -> int:
            for i in range(self.count):
                if self.byIndex(i).selected():
                    return i
            return -1

        @property
        def selectionBottom(self) -> int:
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

        def openPath(self, path: str, focus_name: Union[None, str] = None) -> None:
            target = Path(path)
            if not target.exists():
                print_log("invalid path: '{}'".format(path))
                return
            if target.is_file():
                path = str(target.parent)
                focus_name = target.name
            lister = lister_Default(self._window, path)
            self._window.jumpLister(self._pane, lister, focus_name)

        def touch(self, name: str) -> None:
            if not hasattr(self.lister, "touch"):
                print_log("cannot make file here.")
                return
            dp = Path(self.currentPath, name)
            if dp.exists() and dp.is_file():
                print_log("file '{}' already exists.".format(name))
                return
            self._window.subThreadCall(self.lister.touch, (name,))
            self.refresh()
            self.focus(self._window.cursorFromName(self.fileList, name))

        def mkdir(self, name: str, focus: bool = True) -> None:
            if not hasattr(self.lister, "mkdir"):
                print_log("cannot make directory here.")
                return
            dp = Path(self.currentPath, name)
            if dp.exists() and dp.is_dir():
                print_log("directory '{}' already exists.".format(name))
                return
            self._window.subThreadCall(self.lister.mkdir, (name, None))
            self.refresh()
            if focus:
                sep = "/"
                if os.sep in name or sep in name:
                    name = name.replace(os.sep, sep).split(sep)[0]
                self.focus(self._window.cursorFromName(self.fileList, name))

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

    def shell_exec(path: str, *args) -> bool:
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
            return True
        except:
            print_log("invalid path: '{}'".format(path))
            return False

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

    def hook_enter() -> bool:
        # returning `True` skips default action.

        pane = CPane(window)
        if pane.isBlank:
            pane.focusOther()
            return True

        focus_path = pane.focusedItemPath
        p = Path(focus_path)
        if p.is_dir():
            return False

        if os.path.getsize(focus_path) == 0:
            return shell_exec(focus_path)

        ext = p.suffix

        if EXTENSION_CHECKER.is_image(ext):
            return False

        if EXTENSION_CHECKER.is_archiver(ext):
            return True

        if EXTENSION_CHECKER.is_music(ext) or ext == ".m4a":
            return shell_exec(focus_path)

        if ext == ".pdf":
            sumatra_path = Path(
                USER_PROFILE, r"AppData\Local\SumatraPDF\SumatraPDF.exe"
            )
            if sumatra_path.exists():
                return shell_exec(str(sumatra_path), focus_path)

        if ext in [".xlsx", ".xls"]:
            excel_path = Path(
                r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Excel.lnk"
            )
            if excel_path.exists():
                return shell_exec(str(excel_path), focus_path)

        if ext in [".docx", ".doc"]:
            word_path = Path(
                r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Word.lnk"
            )
            if word_path.exists():
                return shell_exec(str(word_path), focus_path)

        if ext in [".pptx", ".ppt"]:
            ppt_path = Path(
                r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\PowerPoint.lnk"
            )
            if ppt_path.exists():
                return shell_exec(str(ppt_path), focus_path)

        return False

    window.enter_hook = hook_enter

    KEYBINDER.bind("L", window.command_Enter)
    KEYBINDER.bind("Right", window.command_Enter)

    def toggle_hidden() -> None:
        window.showHiddenFile(not window.isHiddenFileVisible())

    KEYBINDER.bind("C-S-H", toggle_hidden)

    def quick_move() -> None:
        pane = CPane(window)
        if not pane.fileList.selected():
            window.command_Select(None)
        window.command_Move(None)

    KEYBINDER.bind("M", quick_move)

    def quick_copy() -> None:
        pane = CPane(window)
        if not pane.fileList.selected():
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

    class DirRule:
        def __init__(self, current_path: str, src_name: str = ".dirnames") -> None:
            self._current_path = current_path
            self._src_name = src_name

        def read_src(self) -> str:
            p = Path(self._current_path)
            for path in p.parents:
                if (f := Path(path, self._src_name)).exists():
                    return f.read_text("utf-8")
            return ""

        def fzf(self) -> str:
            src = self.read_src().strip()
            if len(src) < 1:
                print_log("src file '{}' not found...".format(self._src_name))
                return ""
            src = "\n".join(sorted(sorted(src.splitlines()), key=len))
            try:
                cmd = ["fzf.exe", "--no-sort"]
                proc = subprocess.run(
                    cmd, input=src, capture_output=True, encoding="utf-8"
                )
                result = proc.stdout.strip()
                if proc.returncode == 0:
                    return result
            except Exception as e:
                print(e)
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
            fmt = "{:0" + str(width) + "}"
            return fmt.format(idxs[-1] + 1)

        def get_name(self) -> str:
            line = self.fzf()
            if -1 < (i := line.find("|")):
                line = line[:i].strip()
            if len(line) < 1:
                return ""
            if line.startswith("#"):
                idx = self.get_index()
                return idx + line[1:]
            return line

    def ruled_mkdir() -> None:
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
            return self._exe_path.exists() and self._src_path.exists()

        def invoke(self, search_all: bool = False) -> Callable:
            cmd = self._cmd + ["-all={}".format(search_all)]

            def _find(job_item: ckit.JobItem) -> None:
                job_item.result = None
                if not self.check():
                    return
                delay(100)
                proc = subprocess.run(cmd, capture_output=True, encoding="utf-8")
                result = proc.stdout.strip()
                if result:
                    if proc.returncode != 0:
                        if result:
                            print_log(result)
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

        def apply(self, key: str) -> None:
            mapping = {
                "": False,
                "A-": True,
            }
            for mod, search_all in mapping.items():
                KEYBINDER.bind(mod + key, self.invoke(search_all))

    zyl().apply("C-S-Space")
    zyl().apply("C-S-Z")

    class zyc:
        def __init__(self) -> None:
            self._exe_path = Path(USER_PROFILE, r"Personal\tools\bin\zyc.exe")
            self._cmd = [
                str(self._exe_path),
                "-exclude=_obsolete,node_modules",
                "-stdout=True",
            ]

        def check(self) -> bool:
            return self._exe_path.exists()

        def invoke(self, search_all: bool, offset: int) -> Callable:

            def _find(job_item: ckit.JobItem) -> None:
                job_item.result = None
                if not self.check():
                    return
                pane = CPane(window)
                cmd = self._cmd + [
                    "-all={}".format(search_all),
                    "-offset={}".format(offset),
                    "-cur={}".format(pane.currentPath),
                ]
                delay(100)
                proc = subprocess.run(cmd, capture_output=True, encoding="utf-8")
                result = proc.stdout.strip()
                if result:
                    if proc.returncode != 0:
                        if result:
                            print_log(result)
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

    zyc().apply("Z")

    KEYBINDER.bindmulti(
        {
            "S-F": zyc().invoke(False, 0),
            "C-F": zyc().invoke(True, 0),
        }
    )

    def smart_jump_input() -> None:
        pane = CPane(window)
        result, mod = window.commandLine(
            title="JumpInputSmart",
            auto_complete=True,
            candidate_handler=candidate_Filename(pane.fileList.getLocation()),
            return_modkey=True,
        )
        if result == None:
            return
        result = result.strip()
        if len(result) < 1:
            return
        open_path = Path(pane.currentPath, result)
        if open_path.is_dir():
            if mod == ckit.MODKEY_SHIFT:
                pane.openPath(str(open_path))
            else:
                pane.openPath(str(open_path.parent), str(open_path.name))
        else:
            pane.openPath(str(open_path))
            if mod == ckit.MODKEY_SHIFT:
                shell_exec(str(open_path))

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
            print_log("'{}' already exists.".format(result))
            return

        active_pane.mkdir(result, False)
        extract_path = str(Path(active_pane.currentPath, result))

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

    class Clipper:
        def __init__(self) -> None:
            pass

        @staticmethod
        def targets() -> List[str]:
            pane = CPane(window)
            if pane.isBlank:
                return [pane.currentPath]
            paths = pane.selectedItemPaths
            if len(paths) < 1:
                paths.append(pane.focusedItemPath)
            return paths

        @staticmethod
        def toClipboard(ss: List[str]) -> None:
            if check_log_selected():
                window.command_SetClipboard_LogSelected(None)
                return
            if 0 < len(ss):
                ckit.setClipboardText(LINE_BREAK.join(ss))
                if len(ss) == 1:
                    window.setStatusMessage("Copied: '{}'".format(ss[0]), 2000)
                else:
                    print("\nCopied:")
                    for s in ss:
                        print("- '{}'".format(s))
                    print()

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
        def __init__(self, window: MainWindow, active: bool = True) -> None:
            self._window = window
            self._active = active

        @property
        def pane(self) -> CPane:
            return CPane(self._window, self._active)

        def allItems(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                pane.select(i)

        def toggleAll(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                pane.toggleSelection(i)

        def toTop(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if i <= pane.cursor:
                    pane.select(i)

        def clearToTop(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if i <= pane.cursor:
                    pane.unSelect(i)

        def toBottom(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if pane.cursor <= i:
                    pane.select(i)

        def clearToBottom(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if pane.cursor <= i:
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
            for i in range(pane.count):
                pane.unSelect(i)

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

    SELECTOR = Selector(window)

    KEYBINDER.bindmulti(
        {
            "C-A": SELECTOR.allItems,
            "C-S-A": SELECTOR.toggleAll,
            "U": SELECTOR.clearAll,
            "A-F": SELECTOR.files,
            "A-D": SELECTOR.dirs,
            "S-Home": SELECTOR.toTop,
            "S-A": SELECTOR.toTop,
            "A-S-Home": SELECTOR.clearToTop,
            "A-S-A": SELECTOR.clearToTop,
            "S-End": SELECTOR.toBottom,
            "S-E": SELECTOR.toBottom,
            "A-S-End": SELECTOR.clearToBottom,
            "A-S-E": SELECTOR.clearToBottom,
        }
    )

    def unselect_panes() -> None:
        Selector(window, True).clearAll()
        Selector(window, False).clearAll()

    KEYBINDER.bind("C-U", unselect_panes)

    class SelectionBlock:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

        @property
        def pane(self) -> CPane:
            return CPane(self._window)

        def topOfCurrent(self) -> int:
            pane = self.pane
            if pane.cursor == 0 or not pane.focusedItem.selected():
                return -1
            for i in reversed(range(0, pane.cursor)):
                if i == pane.selectionTop:
                    return i
                if not pane.byIndex(i).selected():
                    return i + 1
            return -1

        def bottomOfCurrent(self) -> int:
            pane = self.pane
            if not pane.focusedItem.selected():
                return -1
            for i in range(pane.cursor + 1, pane.count):
                if i == pane.selectionBottom:
                    return i
                if not pane.byIndex(i).selected():
                    return i - 1
            return -1

        def topOfNext(self) -> int:
            pane = self.pane
            for i in range(pane.cursor + 1, pane.count):
                if pane.byIndex(i).selected():
                    return i
            return -1

        def bottomOfPrevious(self) -> int:
            pane = self.pane
            for i in reversed(range(0, pane.cursor)):
                if pane.byIndex(i).selected():
                    return i
            return -1

        def jumpDown(self) -> None:
            pane = self.pane
            if pane.cursor == pane.count - 1:
                return
            below = pane.byIndex(pane.cursor + 1)
            dest = -1
            if pane.focusedItem.selected():
                if below.selected():
                    dest = self.bottomOfCurrent()
                else:
                    dest = self.topOfNext()
            else:
                if below.selected():
                    dest = pane.cursor + 1
                else:
                    dest = self.topOfNext()
            if dest < 0:
                return
            pane.focus(dest)
            pane.scrollToCursor()

        def jumpUp(self) -> None:
            pane = self.pane
            if pane.cursor == 0:
                return
            above = pane.byIndex(pane.cursor - 1)
            dest = -1
            if pane.focusedItem.selected():
                if above.selected():
                    dest = self.topOfCurrent()
                else:
                    dest = self.bottomOfPrevious()
            else:
                if above.selected():
                    dest = pane.cursor - 1
                else:
                    dest = self.bottomOfPrevious()
            if dest < 0:
                return
            pane.focus(dest)
            pane.scrollToCursor()

    SELECTION_BLOCK = SelectionBlock(window)
    KEYBINDER.bind("A-J", SELECTION_BLOCK.jumpDown)
    KEYBINDER.bind("A-K", SELECTION_BLOCK.jumpUp)

    def focus_bottom_of_dir() -> None:
        pane = CPane(window)
        idx = -1
        for i in range(pane.count):
            if pane.byIndex(i).isdir():
                idx = i
        if idx < 0:
            return
        pane.focus(idx)

    KEYBINDER.bind("A-E", focus_bottom_of_dir)

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

    def on_pdf_viewer(viewer_path: str) -> None:
        def _invoker() -> None:
            if Path(viewer_path).exists():
                pane = CPane(window)
                paths = pane.selectedItemPaths
                if len(paths) < 1:
                    paths.append(pane.focusedItemPath)
                for path in paths:
                    if Path(path).suffix == ".pdf":
                        shell_exec(viewer_path, path)

        return _invoker

    KEYBINDER.bind(
        "A-P",
        on_pdf_viewer(r"C:\Program Files\Adobe\Acrobat DC\Acrobat\Acrobat.exe"),
    )
    KEYBINDER.bind(
        "C-P",
        on_pdf_viewer(r"C:\Program Files\Tracker Software\PDF Editor\PDFXEdit.exe"),
    )

    def on_vscode() -> None:
        vscode_path = Path(USER_PROFILE, r"scoop\apps\vscode\current\Code.exe")
        if vscode_path.exists():
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

        def execute(self, org_path: Path, new_name: str) -> None:
            new_path = org_path.with_name(new_name)
            if new_path.exists():
                print_log("'{}' already exists!".format(new_name))
                return
            try:
                self._window.subThreadCall(org_path.rename, (str(new_path),))
                print_log("Renamed: {}\n     ==> {}".format(org_path.name, new_name))
                self._pane.refresh()
            except Exception as e:
                print(e)

    def rename_substr() -> None:
        renamer = Renamer(window)

        targets = renamer.candidate
        if len(targets) < 1:
            return

        result, mod = window.commandLine(
            "Substr length (Shift from tail)", return_modkey=True
        )

        if not result:
            return

        from_tail = mod == ckit.MODKEY_SHIFT

        for item in targets:
            org_path = Path(item.getFullpath())
            if from_tail:
                stem = org_path.stem
                new_name = stem[: len(stem) - int(result)] + org_path.suffix
            else:
                new_name = org_path.name[int(result) :]

            renamer.execute(org_path, new_name)

    KEYBINDER.bind("S-S", rename_substr)

    def rename_insert() -> None:
        renamer = Renamer(window)

        targets = renamer.candidate
        if len(targets) < 1:
            return

        result, mod = window.commandLine("Append (Shift to head)", return_modkey=True)

        if not result:
            return

        to_head = mod == ckit.MODKEY_SHIFT

        for item in targets:
            org_path = Path(item.getFullpath())
            if to_head:
                new_name = result + org_path.name
            else:
                new_name = org_path.stem + result + org_path.suffix

            renamer.execute(org_path, new_name)

    KEYBINDER.bind("S-I", rename_insert)

    def invoke_renamer(append: Union[bool, None]) -> Callable:
        def _renamer() -> None:
            pane = CPane(window)
            renamer = Renamer(window)
            item = pane.focusedItem
            if not renamer.renamable(item) or pane.isBlank:
                return

            org_path = Path(item.getFullpath())
            offset = len(org_path.stem)
            if append is None:
                sel = [0, offset]
            elif append:
                sel = [offset, offset]
            else:
                sel = [0, 0]

            new_stem = window.commandLine(
                title="NewStem",
                text=org_path.stem,
                selection=sel,
            )

            if not new_stem:
                return

            new_name = new_stem + org_path.suffix
            renamer.execute(org_path, new_name)

        return _renamer

    KEYBINDER.bind("A-N", invoke_renamer(None))
    KEYBINDER.bind("F2", invoke_renamer(None))
    KEYBINDER.bind("N", invoke_renamer(True))
    KEYBINDER.bind("S-N", invoke_renamer(False))

    def duplicate_file() -> None:
        pane = CPane(window)
        src_path = Path(pane.focusedItemPath)
        offset = len(src_path.stem)
        result = window.commandLine(
            title="NewName",
            text=src_path.name,
            selection=[offset, offset],
        )

        if result:
            result = result.strip()
            if len(result) < 1:
                return
            if src_path.is_file() and "." not in result:
                result = result + src_path.suffix
            new_path = src_path.with_name(result)
            if new_path.exists():
                print_log("same item exists!")
                return

            def _copy_as(new_path: str) -> None:
                if Path(src_path).is_dir():
                    shutil.copytree(src_path, new_path)
                else:
                    shutil.copy(src_path, new_path)

            window.subThreadCall(_copy_as, (new_path,))
            pane.refresh()
            pane.focusByName(Path(new_path).name)

    KEYBINDER.bind("S-D", duplicate_file)

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
                found = []
                cursor_offset = 0
                for dd in possible_dests:
                    if dd.startswith(update_info.text):
                        found.append(dd)
                return found, cursor_offset

            result, mod = window.commandLine(
                prompt,
                auto_complete=True,
                candidate_handler=_listup_dests,
                return_modkey=True,
            )
            if not result:
                return

            dir_path = Path(pane.currentPath, result)
            if not dir_path.exists():
                pane.mkdir(result)
            pane.copyToChild(result, items, remove_origin)
            if mod == ckit.MODKEY_SHIFT:
                pane.openPath(str(dir_path))
            else:
                pane.focusByName(result)

        return _mover

    KEYBINDER.bind("A-M", smart_move_to_dir(True))
    KEYBINDER.bind("A-C", smart_move_to_dir(False))

    class TextFileMaker:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

        def invoke(self, extension: str = "") -> None:
            def _func() -> None:
                pane = CPane(self._window)
                if not hasattr(pane.fileList.getLister(), "touch"):
                    return

                basenames = []
                if not pane.isBlank:
                    for file in pane.files:
                        basenames.append(Path(file.getName()).stem)

                def _listup_files(
                    update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
                ) -> tuple:
                    found = []
                    cursor_offset = 0
                    for bn in basenames:
                        if bn.startswith(update_info.text):
                            found.append(bn)
                    return found, cursor_offset

                prompt = "NewFileName"
                if 0 < len(extension):
                    prompt = prompt + " (.{})".format(extension)
                result, mod = window.commandLine(
                    prompt, candidate_handler=_listup_files, return_modkey=True
                )
                if not result:
                    return
                filename = result.strip()
                if len(filename) < 1:
                    return
                if 0 < len(extension):
                    filename = filename + "." + extension
                new_path = Path(pane.currentPath, filename)
                if new_path.exists():
                    print_log("'{}' already exists.".format(filename))
                    return
                pane.touch(filename)
                if mod == ckit.MODKEY_SHIFT:
                    shell_exec(str(new_path))

            return _func

    TEXT_FILE_MAKER = TextFileMaker(window)

    KEYBINDER.bind("T", TEXT_FILE_MAKER.invoke("txt"))
    KEYBINDER.bind("A-T", TEXT_FILE_MAKER.invoke("md"))
    KEYBINDER.bind("C-N", TEXT_FILE_MAKER.invoke(""))

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
        print_log(msg)

    KEYBINDER.bind("A-O", to_obsolete_dir)

    Rect = namedtuple("Rect", ["left", "top", "right", "bottom"])

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
        desktop_path = str(Path(USER_PROFILE, "Desktop"))
        pane = CPane(window, True)
        if pane.currentPath != desktop_path:
            pane.openPath(desktop_path)
        if both_pane:
            window.command_ChdirInactivePaneToOther(None)
            LeftPane(window).activate()

    KEYBINDER.bind("0", lambda: starting_position(False))
    KEYBINDER.bind("S-0", lambda: starting_position(True))

    def open_doc() -> None:
        help_path = str(Path(ckit.getAppExePath(), "doc", "index.html"))
        shell_exec(help_path)

    KEYBINDER.bind("A-H", open_doc)

    def edit_config() -> None:
        dir_path = Path(USER_PROFILE, r"Sync\develop\repo\cfiler")
        if dir_path.exists():
            dp = str(dir_path)
            vscode_path = Path(USER_PROFILE, r"scoop\apps\vscode\current\Code.exe")
            if vscode_path.exists():
                vp = str(vscode_path)
                shell_exec(vp, dp)
            else:
                shell_exec(dp)
        else:
            shell_exec(USER_PROFILE)
            print_log("cannot find repo dir. open user profile instead.")

    KEYBINDER.bind("C-E", edit_config)

    ClonedItem = namedtuple("ClonedItem", ["origin", "clones"])

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

    class PaneDiff:
        _active_pane: CPane
        _inactive_pane: CPane

        def __init__(self) -> None:
            self._active_pane = CPane(window, True)
            self._inactive_pane = CPane(window, False)

        @staticmethod
        def to_hash(path: str) -> str:
            with open(path, "rb") as f:
                digest = hashlib.md5(f.read(64 * 1024)).hexdigest()
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

        def traverse_inactive_pane(self) -> list:
            paths = []
            for item in self._inactive_pane.items:
                if item.isdir():
                    if item.getName().startswith("."):
                        continue
                    for _, _, files in item.walk():
                        for file in files:
                            paths.append(file.getFullpath())
                else:
                    paths.append(item.getFullpath())
            return paths

        def compare(self) -> None:
            def _scan(job_item: ckit.JobItem) -> None:
                targets = self.targets

                job_item.comparable = 0 < len(targets)
                if not job_item.comparable:
                    return

                print_log("comparing md5 hash")

                window.setProgressValue(None)

                table = {}
                for path in self.traverse_inactive_pane():
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
                        print_log("canceled")
                    else:
                        print_log("finished")
                else:
                    print_log("finished (nothing to compare)")

            job = ckit.JobItem(_scan, _finish)
            window.taskEnqueue(job, create_new_queue=False)

    def compare_file_hash() -> None:
        pd = PaneDiff()
        pd.compare()

    def diffinity() -> None:
        exe_path = Path(USER_PROFILE, r"scoop\apps\diffinity\current\Diffinity.exe")
        if not exe_path.exists():
            print_log("cannnot find diffinity.exe...")
            return

        left_pane = LeftPane(window)
        left_selcted = left_pane.selectedItemPaths
        if len(left_selcted) != 1:
            print_log("select just 1 file on left pane.")
            return
        left_path = Path(left_selcted[0])
        if not left_path.is_file():
            print_log("selected item on left pane is not comparable.")
            return
        left_pane = LeftPane(window)

        right_pane = RightPane(window)
        right_selcted = right_pane.selectedItemPaths
        if len(right_selcted) != 1:
            print_log("select just 1 file on right pane.")
            return
        right_path = Path(right_selcted[0])
        if not right_path.is_file():
            print_log("selected item on right pane is not comparable.")
            return

        shell_exec(exe_path, str(left_path), str(right_path))

    def invoke_name_based_selector(select_common: bool) -> Callable:
        def _selector() -> None:
            pane = CPane(window)
            inactive = CPane(window, False)

            names = pane.selectedItemNames if pane.hasSelection else pane.names

            for name in names:
                i = pane.byName(name)
                if select_common:
                    if name in inactive.names:
                        pane.toggleSelection(i)
                else:
                    if name not in inactive.names:
                        pane.toggleSelection(i)

        return _selector

    def select_stem_startswith() -> None:
        pane = CPane(window)
        stems = pane.stems
        stem = Path(pane.focusedItemPath).stem
        ln = len(stem)
        offset = ln
        for i in range(1, ln):
            part = stem[:i]
            found = [s for s in stems if s.startswith(part)]
            if len(found) < 2:
                offset = i - 1
                break
        result, mod = window.commandLine(
            "StartsWith", return_modkey=True, text=stem, selection=[offset, ln]
        )
        if result:
            SELECTOR.stemStartsWith(result, mod == ckit.MODKEY_SHIFT)

    KEYBINDER.bind("Caret", select_stem_startswith)

    def select_stem_endswith() -> None:
        pane = CPane(window)
        stems = pane.stems
        stem = Path(pane.focusedItemPath).stem
        ln = len(stem)
        offset = ln
        for i in range(1, ln):
            part = stem[i:]
            found = [s for s in stems if s.endswith(part)]
            if 1 < len(found):
                offset = i
                break

        result, mod = window.commandLine(
            "EndsWith", return_modkey=True, text=stem, selection=[0, offset]
        )
        if result:
            SELECTOR.stemEndsWith(result, mod == ckit.MODKEY_SHIFT)

    KEYBINDER.bind("4", select_stem_endswith)

    def select_stem_contains() -> None:
        pane = CPane(window)
        result, mod = window.commandLine("Contains", return_modkey=True)
        if result:
            SELECTOR.stemContains(result, mod == ckit.MODKEY_SHIFT)

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

        SELECTOR.byExtension(exts[result], mod == ckit.MODKEY_SHIFT)

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
        items = pane.selectedItems
        for item in items:
            name = item.getName()
            pv = PseudoVoicing(name)
            pv.fix_voicing()
            pv.fix_half_voicing()
            newname = pv.formatted
            if name != newname:
                try:
                    item.rename(newname)
                    print("RENAMED: '{}' ==> '{}'".format(name, newname))
                    item._selected = False
                except Exception as e:
                    print(e)

    class custom_filter:
        def __init__(self, patterns: List[str]) -> None:
            self.patterns = patterns

        def __call__(self, item) -> bool:
            return item.getName() in self.patterns

        def __str__(self) -> str:
            return "[FILTERING]"

    def hide_unselected() -> None:
        pane = CPane(window)
        if pane.hasSelection:
            names = pane.selectedItemNames
            window.subThreadCall(pane.fileList.setFilter, (custom_filter(names),))
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
            if junction_path.exists():
                print_log("'{}' already exists.".format(junction_path))
                return
            try:
                cmd = ["cmd", "/c", "mklink", "/J", str(junction_path), src_path]
                proc = subprocess.run(cmd, capture_output=True, encoding="cp932")
                result = proc.stdout.strip()
                print_log(result)
            except Exception as e:
                print(e)
                print_log("(canceled)")
                return

    def reset_hotkey() -> None:
        window.ini.set("HOTKEY", "activate_vk", "0")
        window.ini.set("HOTKEY", "activate_mod", "0")

    def update_command_list(command_table: dict) -> None:
        for name, func in command_table.items():
            window.launcher.command_list += [(name, Keybinder.wrap(func))]

    update_command_list(
        {
            "MakeJunction": make_junction,
            "ResetHotkey": reset_hotkey,
            "ExtractZipSmart": smart_extract,
            "HideUnselectedItems": hide_unselected,
            "ClearFilter": clear_filter,
            "Diffinity": diffinity,
            "RenamePseudoVoicing": rename_pseudo_voicing,
            "CompareFileHash": compare_file_hash,
            "SelectNameUnique": invoke_name_based_selector(False),
            "SelectNameCommon": invoke_name_based_selector(True),
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
    window.keymap["C-Comma"] = window.command_ConfigMenu
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
        path = window.item.getFullpath()
        window.command_Close(None)
        pyauto.shellExecute(None, path, "", "")

    window.keymap["C-Enter"] = open_original
    window.keymap["C-L"] = open_original

    def copy_content(_) -> None:
        path = Path(window.item.getFullpath())
        enc = window.encoding.encoding
        if enc:
            if window.encoding.bom:
                enc += "-sig"
            content = path.read_text(enc)
            ckit.setClipboardText(content)
            msg = "copied content of '{}' as {} encoding.".format(path.name, enc)
        else:
            msg = "copied nothing: previewing '{}' as binary mode.".format(path.name)
        print("\n{}\n".format(msg))
        window.command_Close(None)

    window.keymap["C-C"] = copy_content


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
    window.keymap["O"] = window.command_ZoomPolicyOriginal
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
    window.keymap["F"] = window.command_ZoomPolicyFit
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

    def open_original(_) -> None:
        item = window.items[window.cursor]
        path = item.getFullpath()
        window.command_Close(None)
        pyauto.shellExecute(None, path, "", "")

    window.keymap["C-Enter"] = open_original
    window.keymap["C-L"] = open_original
