import datetime
import hashlib
import inspect
import os
import shutil
import subprocess

from pathlib import Path
from typing import Callable

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
from cfiler_filelist import FileList, item_Base, lister_Default, item_Empty

# https://github.com/crftwr/cfiler/blob/master/cfiler_listwindow.py
from cfiler_listwindow import ListWindow

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


def runExe(path: str, *args) -> None:
    if type(path) is not str:
        path = str(path)
    if not Path(path).exists():
        print("invalid path: '{}'".format(path))
        return
    params = []
    for arg in args:
        if len(arg.strip()):
            if " " in arg:
                params.append('"{}"'.format(arg))
            else:
                params.append(arg)
    pyauto.shellExecute(None, path, " ".join(params), "")


def configure(window: MainWindow):

    def reset_default_keys(keys: list) -> None:
        for key in keys:

            def _do_nothing(_):
                pass

            window.keymap[key] = _do_nothing

    reset_default_keys(
        [
            "Period",
            "S-Period",
        ]
    )

    def apply_cfiler_command(mapping: dict) -> None:
        for key, func in mapping.items():
            window.keymap[key] = func

    apply_cfiler_command(
        {
            "Q": window.command_CancelTask,
            "C-Q": window.command_Quit,
            "A-F4": window.command_Quit,
            "C-Comma": window.command_ConfigMenu,
            "C-S-Comma": window.command_ConfigMenu2,
            "C-L": window.command_Execute,
            "N": window.command_Rename,
            "A-C-H": window.command_JumpHistory,
            "C-D": window.command_Delete,
            "P": window.command_FocusOther,
            "C-L": window.command_FocusOther,
            "O": window.command_ChdirActivePaneToOther,
            "S-O": window.command_ChdirInactivePaneToOther,
            "A": window.command_CursorTop,
            "E": window.command_CursorBottom,
            "Home": window.command_CursorTop,
            "End": window.command_CursorBottom,
            "J": window.command_CursorDown,
            "K": window.command_CursorUp,
            "C-S-P": window.command_CommandLine,
            "C-S-N": window.command_Mkdir,
            "H": window.command_GotoParentDir,
            "A-C": window.command_ContextMenu,
            "A-S-C": window.command_ContextMenuDir,
        }
    )

    class Keybinder:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

        @staticmethod
        def wrap(func: Callable) -> Callable:
            if inspect.signature(func).parameters.items():

                def _callback_with_arg(arg):
                    func(arg)

                return _callback_with_arg

            def _callback(_):
                func()

            return _callback

        def bind(self, key: str, func: Callable) -> None:
            self._window.keymap[key] = self.wrap(func)

    KEYBINDER = Keybinder(window)

    class JumpList:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

        def update(self, jump_table: dict) -> None:
            for name, path in jump_table.items():
                p = Path(path)
                try:
                    if p.exists() and p.is_dir():
                        self._window.jump_list += [(name, str(p))]
                except Exception as e:
                    print(e)

        def jump(self) -> None:

            wnd = self._window
            pos = wnd.centerOfFocusedPaneInPixel()
            list_window = ListWindow(
                x=pos[0],
                y=pos[1],
                min_width=40,
                min_height=1,
                max_width=wnd.width() - 5,
                max_height=wnd.height() - 3,
                parent_window=wnd,
                ini=wnd.ini,
                title="Jump (other pane with Shift)",
                items=wnd.jump_list,
                initial_select=0,
                onekey_search=False,
                onekey_decide=False,
                return_modkey=True,
                keydown_hook=None,
                statusbar_handler=None,
            )
            wnd.enable(False)
            list_window.messageLoop()
            result, mod = list_window.getResult()
            wnd.enable(True)
            wnd.activate()
            list_window.destroy()

            if result < 0:
                return

            dest = wnd.jump_list[result][1]
            modified = mod == ckit.MODKEY_SHIFT
            active = CPane(wnd, True)
            other = CPane(wnd, False)
            if modified:
                other.openPath(dest)
                active.focusOther()
            else:
                active.openPath(dest)

    JUMP_LIST = JumpList(window)

    JUMP_LIST.update(
        {
            "Desktop": str(Path(USER_PROFILE, "Desktop")),
            "Scan": r"X:\scan",
            "Dropbox Share": str(
                Path(USER_PROFILE, "Dropbox", "_sharing", "_yuhikaku")
            ),
        }
    )

    KEYBINDER.bind("SemiColon", JUMP_LIST.jump)

    class CPane:
        def __init__(self, window: MainWindow, active: bool = True) -> None:
            self._window = window
            if active:
                self._pane = self._window.activePane()
            else:
                self._pane = self._window.inactivePane()

        @property
        def entity(self):
            return self._pane

        def repaint(self, option: PaintOption = PO.All) -> None:
            self._window.paint(option)

        def refresh(self) -> None:
            self._window.subThreadCall(self.fileList.refresh, ())
            self.fileList.applyItems()

        @property
        def dirs(self) -> item_Base:
            items = []
            for i in range(self.count):
                item = self.byIndex(i)
                if item.isdir():
                    items.append(item)
            return items

        @property
        def files(self) -> item_Base:
            items = []
            for i in range(self.count):
                item = self.byIndex(i)
                if not item.isdir():
                    items.append(item)
            return items

        @property
        def history(self) -> History:
            return self._pane.history

        def appendHistory(self, path: str) -> History:
            p = Path(path)
            lister = self._pane.file_list.getLister()
            visible = isinstance(lister, lister_Default)
            return self._pane.history.append(str(p.parent), p.name, visible, False)

        @property
        def cursor(self) -> int:
            return self._pane.cursor

        def focus(self, i: int) -> None:
            self._pane.cursor = i
            self.scrollToCursor()

        def byName(self, name: str) -> int:
            i = self.fileList.indexOf(name)
            if i < 0:
                return 0
            return i

        def focusByName(self, name: str) -> None:
            self.focus(self.byName(name))

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
            for i in range(self.count):
                item = self.byIndex(i)
                names.append(item.getName())
            return names

        @property
        def extensions(self) -> list:
            exts = []
            for i in range(self.count):
                path = Path(self.pathByIndex(i))
                ext = path.suffix.replace(".", "")
                if path.is_file() and ext not in exts:
                    exts.append(ext)
            return exts

        @property
        def selectedItems(self) -> list:
            items = []
            for i in range(self.count):
                item = self.byIndex(i)
                if item.selected():
                    items.append(item)
            return items

        @property
        def selectedItemPaths(self) -> list:
            paths = []
            for i in range(self.count):
                item = self.byIndex(i)
                if item.selected():
                    path = self.pathByIndex(i)
                    paths.append(path)
            return paths

        @property
        def focusedItem(self) -> item_Base:
            return self.byIndex(self.cursor)

        def pathByIndex(self, i: int) -> str:
            item = self.byIndex(i)
            return str(Path(self.currentPath, item.getName()))

        @property
        def focusItemPath(self) -> str:
            return self.pathByIndex(self.cursor)

        def finishSelect(self) -> None:
            self.repaint(PO.FocusedItems | PO.FocusedHeader)

        def toggleSelect(self, i: int) -> None:
            self.fileList.selectItem(i, None)
            self.finishSelect()

        def select(self, i: int) -> None:
            self.fileList.selectItem(i, True)
            self.finishSelect()

        def unSelect(self, i: int) -> None:
            self.fileList.selectItem(i, False)
            self.finishSelect()

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

        def openName(self, name: str) -> bool:
            path = Path(self.currentPath, name)
            if not path.exists() or path.is_file():
                print("invalid dir path: '{}'".format(path))
                return False
            lister = lister_Default(self._window, str(path))
            self._window.jumpLister(self._pane, lister)
            return True

        def openPath(self, path: str) -> bool:
            if not Path(path).exists() or Path(path).is_file():
                print("invalid dir path: '{}'".format(path))
                return False
            lister = lister_Default(self._window, path)
            self._window.jumpLister(self._pane, lister)
            return True

        def touch(self, name: str) -> None:
            if not hasattr(self.lister, "touch"):
                print("cannot make file here.")
                return
            dp = Path(self.currentPath, name)
            if dp.exists() and dp.is_file():
                print("file '{}' already exists.".format(name))
                return
            self._window.subThreadCall(self.lister.touch, (name,))
            self.refresh()
            self.focus(self._window.cursorFromName(self.fileList, name))

        def mkdir(self, name: str) -> None:
            if not hasattr(self.lister, "mkdir"):
                print("cannot make directory here.")
                return
            dp = Path(self.currentPath, name)
            if dp.exists() and dp.is_dir():
                print("directory '{}' already exists.".format(name))
                return
            self._window.subThreadCall(self.lister.mkdir, (name, None))
            self.refresh()
            self.focus(self._window.cursorFromName(self.fileList, name))

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

    def fetch_items(delete_origin: bool = False):
        active_pane = CPane(window, True)
        inactive_pane = CPane(window, False)

        if not hasattr(active_pane.lister, "getCopyDst"):
            return

        items = inactive_pane.selectedItems

        if len(items) < 1:
            return

        if delete_origin:
            mode = "m"
        else:
            mode = "c"
        window._copyMoveCommon(
            inactive_pane.entity,
            inactive_pane.lister,
            active_pane.lister,
            items,
            mode,
            inactive_pane.fileList.getFilter(),
        )

    KEYBINDER.bind("S-C", lambda: fetch_items(False))
    KEYBINDER.bind("S-X", lambda: fetch_items(True))

    def quick_move() -> None:
        pane = CPane(window)
        if not pane.fileList.selected():
            window.command_Select(None)
        window.command_Move(None)

    KEYBINDER.bind("C-X", quick_move)

    def quick_copy() -> None:
        pane = CPane(window)
        if not pane.fileList.selected():
            window.command_Select(None)
        window.command_Copy(None)

    KEYBINDER.bind("C-C", quick_copy)

    def history_back():
        pane = CPane(window)
        hist = pane.history
        if 1 < len(hist.items):
            p = hist.items[1][0]
            pane.openPath(p)

    KEYBINDER.bind("Back", history_back)

    def swap_pane() -> None:
        pane = CPane(window, True)
        current_path = pane.currentPath
        other_pane = CPane(window, False)
        other_path = other_pane.currentPath
        pane.openPath(other_path)
        other_pane.openPath(current_path)

    KEYBINDER.bind("A-S", swap_pane)

    def zymd():
        exe_path = Path(USER_PROFILE, r"Personal\tools\bin\zymd.exe")
        if exe_path.exists():
            pane = CPane(window)
            cmd = [
                str(exe_path),
                "-cur={}".format(pane.currentPath),
                "-stdout=True",
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE)
            result = proc.stdout.decode("utf-8").strip()
            if proc.returncode != 0:
                print(result)
                return
            pane.mkdir(result)

    KEYBINDER.bind("A-N", zymd)

    class zyl:
        def __init__(self) -> None:
            self._exe_path = Path(USER_PROFILE, r"Personal\tools\bin\zyl.exe")
            self._src_path = Path(USER_PROFILE, r"Personal\launch.yaml")

        def check(self) -> bool:
            return self._exe_path.exists() and self._src_path.exists()

        def invoke(self, active_pane: bool = True) -> Callable:
            def _func() -> None:
                if not self.check():
                    return
                pane = CPane(window, active_pane)
                cmd = [
                    str(self._exe_path),
                    "-src={}".format(self._src_path),
                    "-all=False",
                    "-exclude=_obsolete,node_modules",
                    "-stdout=True",
                ]
                proc = subprocess.run(cmd, stdout=subprocess.PIPE)
                result = proc.stdout.decode("utf-8").strip()
                if proc.returncode != 0:
                    if result:
                        print(result)
                    return
                pane.openPath(result)
                if not active_pane:
                    pane.focusOther()

            return _func

    KEYBINDER.bind("Y", zyl().invoke(True))
    KEYBINDER.bind("S-Y", zyl().invoke(False))

    class zyc:
        def __init__(self, search_all: bool) -> None:
            self._exe_path = Path(USER_PROFILE, r"Personal\tools\bin\zyc.exe")
            self._cmd = [
                str(self._exe_path),
                "-exclude=_obsolete,node_modules",
                "-stdout=True",
                "-all={}".format(search_all),
            ]

        def check(self) -> bool:
            return self._exe_path.exists()

        def invoke(self, offset: int) -> Callable:
            def _func() -> None:
                if not self.check():
                    return
                pane = CPane(window)
                cmd = self._cmd + [
                    "-offset={}".format(offset),
                    "-cur={}".format(pane.currentPath),
                ]
                proc = subprocess.run(cmd, stdout=subprocess.PIPE)
                result = proc.stdout.decode("utf-8").strip()
                if result:
                    if proc.returncode != 0:
                        if result:
                            print(result)
                        return
                    if Path(result).is_dir():
                        pane = CPane(window)
                        pane.openPath(result)
                    else:
                        runExe(result)
                        pane.appendHistory(result)

            return _func

    KEYBINDER.bind("Z", zyc(False).invoke(-1))
    KEYBINDER.bind("A-Z", zyc(True).invoke(-1))
    KEYBINDER.bind("S-Z", zyc(False).invoke(1))
    KEYBINDER.bind("A-S-Z", zyc(True).invoke(1))
    KEYBINDER.bind("S-F", zyc(False).invoke(0))
    KEYBINDER.bind("C-S-F", zyc(True).invoke(0))

    def smart_jump_input():
        pane = CPane(window)
        result, mod = window.commandLine(
            title="JumpInputSmart",
            auto_complete=True,
            autofix_list=["\\/", "."],
            candidate_handler=candidate_Filename(pane.fileList.getLocation()),
            return_modkey=True,
        )
        if result == None:
            return
        result = result.strip()
        if len(result) < 1:
            return
        open_path = Path(pane.currentPath, result)
        if not open_path.exists():
            print("invalid-path!")
            return
        if open_path.is_dir():
            if mod == ckit.MODKEY_SHIFT:
                CPane(window, False).openPath(str(open_path))
            else:
                pane.openName(result)
        else:
            runExe(open_path)
            pane.appendHistory(str(open_path))

    KEYBINDER.bind("F", smart_jump_input)

    def smart_copy_name():
        pane = CPane(window)
        names = []
        for i in range(pane.count):
            item = pane.byIndex(i)
            if item.selected():
                names.append(item.getName())

        if len(names) < 1:
            name = pane.focusedItem.getName()
            ckit.setClipboardText(name)
            print("\ncopied focused item name:\n{}".format(name))
            return

        lines = LINE_BREAK.join(names)
        ckit.setClipboardText(lines)
        print("\ncopied name of items below:")
        for name in names:
            print("- {}".format(Path(name).name))

    KEYBINDER.bind("C-S-C", smart_copy_name)

    def smart_copy_path():
        pane = CPane(window)
        paths = []
        for i in range(pane.count):
            item = pane.byIndex(i)
            if item.selected():
                paths.append(pane.pathByIndex(i))

        if len(paths) < 1:
            ckit.setClipboardText(pane.currentPath)
            print("\ncopied current directory path:\n{}".format(pane.currentPath))
            return

        lines = LINE_BREAK.join(paths)
        ckit.setClipboardText(lines)
        print("\ncopied fullpath of items below:")
        for path in paths:
            print("- {}".format(Path(path).name))

    KEYBINDER.bind("C-A-P", smart_copy_path)

    def smart_enter():
        pane = CPane(window)
        if pane.isBlank:
            pane.focusOther()
            return
        if pane.focusedItem.isdir():
            window.command_Enter(None)
        else:
            window.command_Execute(None)

    KEYBINDER.bind("L", smart_enter)

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

        def allFiles(self) -> None:
            pane = self.pane
            self.clearAll()
            idx = []
            for i in range(pane.count):
                if not pane.byIndex(i).isdir():
                    pane.select(i)
                    idx.append(i)
            if 0 < len(idx):
                pane.focus(idx[0])

        def allDirs(self) -> None:
            pane = self.pane
            self.clearAll()
            idx = []
            for i in range(pane.count):
                if pane.byIndex(i).isdir():
                    pane.select(i)
                    idx.append(i)
            if 0 < len(idx):
                pane.focus(idx[-1])

        def clearAll(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                pane.unSelect(i)

        def clearFiles(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if pane.byIndex(i).isdir():
                    pane.unSelect(i)

        def clearDirs(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if not pane.byIndex(i).isdir():
                    pane.unSelect(i)

        def byFunction(self, func: Callable) -> None:
            pane = self.pane
            self.clearAll()
            idx = []
            for i in range(pane.count):
                path = pane.pathByIndex(i)
                if func(path):
                    pane.select(i)
                    idx.append(i)
            if 0 < len(idx):
                pane.focus(idx[0])

        def byExtension(self, s: str) -> None:
            def selector(path: str) -> None:
                return Path(path).suffix == s

            self.byFunction(selector)

        def stemContains(self, s: str) -> None:
            def selector(path: str) -> None:
                return s in Path(path).stem

            self.byFunction(selector)

        def stemStartsWith(self, s: str) -> None:
            def selector(path: str) -> None:
                return Path(path).stem.startswith(s)

            self.byFunction(selector)

        def stemEndsWith(self, s: str) -> None:
            def selector(path: str) -> None:
                return Path(path).stem.endswith(s)

            self.byFunction(selector)

        def toTop(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if i <= pane.cursor:
                    pane.select(i)

        def toEnd(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if pane.cursor <= i:
                    pane.select(i)

    SELECTOR = Selector(window)

    KEYBINDER.bind("C-A", SELECTOR.allItems)
    KEYBINDER.bind("C-U", SELECTOR.clearAll)
    KEYBINDER.bind("A-F", SELECTOR.allFiles)
    KEYBINDER.bind("A-S-F", SELECTOR.clearDirs)
    KEYBINDER.bind("A-D", SELECTOR.allDirs)
    KEYBINDER.bind("A-S-D", SELECTOR.clearFiles)
    KEYBINDER.bind("S-Home", SELECTOR.toTop)
    KEYBINDER.bind("S-A", SELECTOR.toTop)
    KEYBINDER.bind("S-End", SELECTOR.toEnd)
    KEYBINDER.bind("S-E", SELECTOR.toEnd)

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
                dest = pane.count - 1
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
                dest = 0
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

    def duplicate_pane():
        pane = CPane(window, True)
        other = CPane(window, False)
        other.openPath(pane.currentPath)
        pane.focusOther()
        other.focus(pane.cursor)

    KEYBINDER.bind("W", duplicate_pane)

    def open_on_explorer():
        pane = CPane(window, True)
        runExe(pane.currentPath)

    KEYBINDER.bind("C-S-E", open_on_explorer)

    def open_to_other():
        active_pane = CPane(window, True)
        inactive_pane = CPane(window, False)
        inactive_pane.openPath(active_pane.focusItemPath)
        active_pane.focusOther()

    KEYBINDER.bind("S-L", open_to_other)

    def open_parent_to_other():
        active_pane = CPane(window, True)
        parent = str(Path(active_pane.currentPath).parent)
        current_name = str(Path(active_pane.currentPath).name)
        inactive_pane = CPane(window, False)
        inactive_pane.openPath(parent)
        active_pane.focusOther()
        inactive_pane.focusByName(current_name)

    KEYBINDER.bind("U", open_parent_to_other)

    def on_vscode():
        vscode_path = Path(USER_PROFILE, r"scoop\apps\vscode\current\Code.exe")
        if vscode_path.exists():
            pane = CPane(window)
            runExe(str(vscode_path), pane.currentPath)

    KEYBINDER.bind("V", on_vscode)

    def duplicate_with_name():
        pane = CPane(window)
        focus_path = Path(pane.focusItemPath)
        result = window.commandLine(
            title="NewName",
            text=focus_path.name,
            selection=[0, len(focus_path.stem)],
        )

        if result:
            result = result.strip()
            if len(result) < 1:
                return
            new_path = focus_path.with_name(result)
            if new_path.exists():
                print("same item exists!")
                return
            try:
                if focus_path.is_dir():
                    shutil.copytree(str(focus_path), new_path)
                    CPane(window, False).openPath(new_path)
                    pane.focusOther()
                else:
                    shutil.copy(str(focus_path), new_path)
            except Exception as e:
                print(e)

    KEYBINDER.bind("S-D", duplicate_with_name)

    class TextFileMaker:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

        def invoke(self, extension: str = "") -> None:
            def _func() -> None:
                pane = CPane(self._window)
                if not hasattr(pane.fileList.getLister(), "touch"):
                    return

                prompt = "NewFileName"
                if 0 < len(extension):
                    prompt = prompt + " (.{})".format(extension)
                result = window.commandLine(prompt)
                if not result:
                    return
                filename = result.strip()
                if len(filename) < 1:
                    return
                if 0 < len(extension):
                    filename = filename + "." + extension
                if Path(pane.currentPath, filename).exists():
                    print("'{}' already exists.".format(filename))
                    return
                pane.touch(filename)

            return _func

    TEXT_FILE_MAKER = TextFileMaker(window)

    KEYBINDER.bind("T", TEXT_FILE_MAKER.invoke("txt"))
    KEYBINDER.bind("C-T", TEXT_FILE_MAKER.invoke("md"))
    KEYBINDER.bind("S-T", TEXT_FILE_MAKER.invoke(""))

    def to_obsolete_dir():
        pane = CPane(window)

        items = []
        for i in range(pane.count):
            item = pane.byIndex(i)
            if item.selected() and hasattr(item, "delete"):
                items.append(item)
        if len(items) < 1:
            return

        dest_name = "_obsolete"
        pane.mkdir(dest_name)

        child_lister = pane.lister.getChild(dest_name)
        window._copyMoveCommon(
            pane.entity,
            pane.lister,
            child_lister,
            items,
            "m",
            pane.fileList.getFilter(),
        )
        child_lister.destroy()

    KEYBINDER.bind("A-O", to_obsolete_dir)

    def reload_config():
        window.configure()
        window.command_MoveSeparatorCenter(None)
        LeftPane(window).activate()
        ts = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
        print("{} reloaded config.py\n".format(ts))

    KEYBINDER.bind("C-R", reload_config)
    KEYBINDER.bind("F5", reload_config)

    def open_doc():
        help_path = str(Path(ckit.getAppExePath(), "doc", "index.html"))
        runExe(help_path)

    KEYBINDER.bind("A-H", open_doc)

    def edit_config():
        dir_path = Path(USER_PROFILE, r"Sync\develop\repo\cfiler")
        if dir_path.exists():
            dp = str(dir_path)
            vscode_path = Path(USER_PROFILE, r"scoop\apps\vscode\current\Code.exe")
            if vscode_path.exists():
                vp = str(vscode_path)
                runExe(vp, dp)
            else:
                runExe(dp)
        else:
            runExe(USER_PROFILE)
            print("cannot find repo dir. open user profile instead.")

    KEYBINDER.bind("C-E", edit_config)

    def compare_file_hash():
        active_pane = CPane(window, True)
        if len(active_pane.files) < 1:
            print("no files to compare in active pane.")
            return

        inactive_pane = CPane(window, False)
        if len(inactive_pane.files) < 1:
            print("no files to compare in inactive pane.")
            return

        print("==================")
        print(" compare md5 hash ")
        print("==================")

        table = {}
        window.setProgressValue(None)

        def _storeInactivePaneHash(job_item: ckit.JobItem) -> None:
            for item in inactive_pane.files:
                if job_item.isCanceled():
                    break
                if job_item.waitPaused():
                    window.setProgressValue(None)
                name = str(
                    Path(item.getFullpath()).relative_to(inactive_pane.currentPath)
                )
                digest = hashlib.md5(item.open().read(64 * 1024)).hexdigest()
                table[digest] = table.get(digest, []) + [name]

        def _clearSelection(job_item: ckit.JobItem) -> None:
            window.clearProgress()
            if job_item.isCanceled():
                return
            if job_item.waitPaused():
                window.setProgressValue(None)
            Selector(window, True).clearAll()
            Selector(window, False).clearAll()

        def _compareHash(job_item: ckit.JobItem) -> None:
            window.setProgressValue(None)
            for item in active_pane.files:
                if job_item.isCanceled():
                    break
                if job_item.waitPaused():
                    window.setProgressValue(None)
                name = item.getName()
                digest = hashlib.md5(item.open().read(64 * 1024)).hexdigest()
                if digest in table:
                    active_pane.select(active_pane.byName(name))
                    for n in table[digest]:
                        print("'{}' === '{}'".format(name, n))

        def _finish(job_item: ckit.JobItem) -> None:
            window.clearProgress()
            if job_item.isCanceled():
                print("Canceled.\n")
                return
            print("==================")
            print("     FINISHED     ")
            print("==================")

        job_prepare = ckit.JobItem(_storeInactivePaneHash, _clearSelection)
        job_compare = ckit.JobItem(_compareHash, _finish)
        window.taskEnqueue(job_prepare, create_new_queue=False)
        window.taskEnqueue(job_compare, create_new_queue=False)

    def diffinity():
        exe_path = Path(USER_PROFILE, r"scoop\apps\diffinity\current\Diffinity.exe")
        if not exe_path.exists():
            print("cannnot find diffinity.exe...")
            return

        left_pane = LeftPane(window)
        left_selcted = left_pane.selectedItemPaths
        if len(left_selcted) != 1:
            print("select just 1 file on left pane.")
            return
        left_path = Path(left_selcted[0])
        if not left_path.is_file():
            print("selected item on left pane is not comparable.")
            return
        left_pane = LeftPane(window)

        right_pane = RightPane(window)
        right_selcted = right_pane.selectedItemPaths
        if len(right_selcted) != 1:
            print("select just 1 file on right pane.")
            return
        right_path = Path(right_selcted[0])
        if not right_path.is_file():
            print("selected item on right pane is not comparable.")
            return

        param = '"{}" "{}"'.format(left_path, right_path)
        runExe(exe_path, param)

    def select_name_common():
        inactive = CPane(window, False)
        other_names = inactive.names
        pane = CPane(window)
        for i in range(pane.count):
            item = pane.byIndex(i)
            if item.getName() in other_names:
                pane.select(i)
            else:
                pane.unSelect(i)

    def select_name_unique():
        inactive = CPane(window, False)
        other_names = inactive.names
        pane = CPane(window)
        for i in range(pane.count):
            item = pane.byIndex(i)
            if item.getName() in other_names:
                pane.unSelect(i)
            else:
                pane.select(i)

    def select_stem_startswith():
        result = window.commandLine("StartsWith")
        if result:
            SELECTOR.stemStartsWith(result)

    def select_stem_endsswith():
        result = window.commandLine("EndsWith")
        if result:
            SELECTOR.stemEndsWith(result)

    def select_stem_contains():
        result = window.commandLine("Contains")
        if result:
            SELECTOR.stemContains(result)

    def select_byext():
        pane = CPane(window)
        exts = pane.extensions

        def _listup_extensions(update_info) -> tuple:
            found = []
            cursor_offset = 0
            for e in exts:
                if e.startswith(update_info.text):
                    found.append(e)
            return found, cursor_offset

        result = window.commandLine(
            "Extension", auto_complete=True, candidate_handler=_listup_extensions
        )
        if result:
            if not result.startswith("."):
                result = "." + result
            SELECTOR.byExtension(result)

    KEYBINDER.bind("S-X", select_byext)

    def update_command_list(command_table: dict) -> None:
        for name, func in command_table.items():
            window.launcher.command_list += [(name, Keybinder.wrap(func))]

    update_command_list(
        {
            "Diffinity": diffinity,
            "CompareFileHash": compare_file_hash,
            "SelectNameUnique": select_name_unique,
            "SelectNameCommon": select_name_common,
            "SelectStemStartsWith": select_stem_startswith,
            "SelectStemEndsWith": select_stem_endsswith,
            "SelectStemContains": select_stem_contains,
            "SelectByExtension": select_byext,
        }
    )


def configure_TextViewer(window: ckit.TextWindow):
    window.keymap["J"] = window.command_ScrollDown
    window.keymap["K"] = window.command_ScrollUp

    def open_original(_):
        path = window.item.getFullpath()
        window.command_Close(None)
        runExe(path)

    window.keymap["O"] = open_original


def configure_ListWindow(window: ckit.TextWindow):
    window.keymap["J"] = window.command_CursorDown
    window.keymap["K"] = window.command_CursorUp
    for mod in ["", "S-"]:
        window.keymap[mod + "Space"] = window.command_Enter
