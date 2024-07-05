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
from cfiler_filelist import FileList, item_Base, lister_Default

# https://github.com/crftwr/cfiler/blob/master/cfiler_listwindow.py
from cfiler_listwindow import ListWindow


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


def bind(func: Callable):
    if inspect.signature(func).parameters.items():

        def _callback_with_arg(arg):
            func(arg)

        return _callback_with_arg

    def _callback(_):
        func()

    return _callback


def configure(window: MainWindow):

    def reset_default_keys(keys: list) -> None:
        for key in keys:

            def _do_nothing(_):
                pass

            window.keymap[key] = _do_nothing

    reset_default_keys(
        [
            "Q",
            "Period",
            "S-Period",
        ]
    )

    def apply_cfiler_command(mapping: dict) -> None:
        for key, func in mapping.items():
            window.keymap[key] = func

    apply_cfiler_command(
        {
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
            "O": window.command.ChdirActivePaneToOther,
            "S-O": window.command.ChdirInactivePaneToOther,
            "A": window.command_CursorTop,
            "E": window.command_CursorBottom,
            "Home": window.command_CursorTop,
            "End": window.command_CursorBottom,
            "J": window.command_CursorDown,
            "K": window.command_CursorUp,
        }
    )

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

        def jump(self, active_pane: bool = True) -> None:
            if active_pane:
                title = "Jump on active pane"
            else:
                title = "Jump on inactive pane"

            wnd = self._window
            pos = wnd.centerOfFocusedPaneInPixel()
            list_window = ListWindow(
                pos[0],
                pos[1],
                5,
                1,
                wnd.width() - 5,
                wnd.height() - 3,
                wnd,
                wnd.ini,
                title,
                wnd.jump_list,
                initial_select=0,
            )
            wnd.enable(False)
            list_window.messageLoop()
            result = list_window.getResult()
            wnd.enable(True)
            wnd.activate()
            list_window.destroy()

            if result < 0:
                return

            dest = wnd.jump_list[result][1]
            CPane(wnd, active_pane).openPath(dest)

        def invoke_jumper(self, active_pane: bool) -> None:
            def _func(_) -> None:
                self.jump(active_pane)

            return _func

        def apply(self, mapping: dict) -> None:
            for key, active_pane in mapping.items():
                self._window.keymap[key] = self.invoke_jumper(active_pane)

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

    JUMP_LIST.apply(
        {
            "C-J": True,
            "C-S-J": False,
        }
    )

    class CPane:
        def __init__(self, window: MainWindow, active: bool = True) -> None:
            self._window = window
            if active:
                self._pane = self._window.activePane()
            else:
                self._pane = self._window.inactivePane()

        def repaint(self, option: PaintOption = PO.All) -> None:
            self._window.paint(option)

        def refresh(self) -> None:
            self._window.subThreadCall(self.file_list.refresh, ())
            self.file_list.applyItems()

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
            i = self.file_list.indexOf(name)
            if i < 0:
                return 0
            return i

        def focusByName(self, name: str) -> None:
            self.focus(self.byName(name))

        def focusOther(self) -> None:
            self._window.command_FocusOther(None)

        @property
        def file_list(self) -> FileList:
            return self._pane.file_list

        @property
        def scroll_info(self) -> ckit.ScrollInfo:
            return self._pane.scroll_info

        @property
        def current_path(self) -> str:
            return self.file_list.getLocation()

        @property
        def count(self) -> int:
            return self.file_list.numItems()

        def byIndex(self, i: int) -> item_Base:
            return self.file_list.getItem(i)

        @property
        def names(self) -> list:
            names = []
            for i in range(self.count):
                item = self.byIndex(i)
                names.append(item.getName())
            return names

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
            return str(Path(self.current_path, item.getName()))

        @property
        def focusItemPath(self) -> str:
            return self.pathByIndex(self.cursor)

        def toggleSelect(self, i: int) -> None:
            self.file_list.selectItem(i, None)

        def select(self, i: int) -> None:
            self.file_list.selectItem(i, True)

        def unSelect(self, i: int) -> None:
            self.file_list.selectItem(i, False)

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
            self.scroll_info.makeVisible(i, self._window.fileListItemPaneHeight(), 1)
            self.repaint(PO.FocusedItems)

        def scrollToCursor(self) -> None:
            self.scrollTo(self.cursor)

        def openName(self, name: str) -> bool:
            path = Path(self.current_path, name)
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
            if not hasattr(self.file_list.getLister(), "touch"):
                print("cannot make file here.")
                return
            dp = Path(self.current_path, name)
            if dp.exists() and dp.is_file():
                print("file '{}' already exists.".format(name))
                return
            self._window.subThreadCall(self.file_list.getLister().touch, (name,))
            self.refresh()
            self.focus(self._window.cursorFromName(self.file_list, name))

        def mkdir(self, name: str) -> None:
            if not hasattr(self.file_list.getLister(), "mkdir"):
                print("cannot make directory here.")
                return
            dp = Path(self.current_path, name)
            if dp.exists() and dp.is_dir():
                print("directory '{}' already exists.".format(name))
                return
            self._window.subThreadCall(self.file_list.getLister().mkdir, (name, None))
            self.refresh()
            self.focus(self._window.cursorFromName(self.file_list, name))

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

    def quick_move():
        pane = CPane(window)
        if not pane.file_list.selected():
            window.command_Select(None)
        window.command_Move(None)

    window.keymap["C-X"] = bind(quick_move)

    def quick_copy():
        pane = CPane(window)
        if not pane.file_list.selected():
            window.command_Select(None)
        window.command_Copy(None)

    window.keymap["C-C"] = bind(quick_copy)

    def history_back():
        pane = CPane(window)
        hist = pane.history
        if 1 < len(hist.items):
            p = hist.items[1][0]
            pane.openPath(p)

    window.keymap["Back"] = bind(history_back)

    def swap_pane() -> None:
        pane = CPane(window, True)
        current_path = pane.current_path
        other_pane = CPane(window, False)
        other_path = other_pane.current_path
        pane.openPath(other_path)
        other_pane.openPath(current_path)

    window.keymap["A-S"] = bind(swap_pane)

    def zymd():
        exe_path = Path(USER_PROFILE, r"Personal\tools\bin\zymd.exe")
        if exe_path.exists():
            pane = CPane(window)
            cmd = [
                str(exe_path),
                "-cur={}".format(pane.current_path),
                "-stdout=True",
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE)
            result = proc.stdout.decode("utf-8").strip()
            if proc.returncode != 0:
                print(result)
                return
            pane.mkdir(result)

    window.keymap["A-N"] = bind(zymd)

    def zyl():
        exe_path = Path(USER_PROFILE, r"Personal\tools\bin\zyl.exe")
        src_path = Path(USER_PROFILE, r"Personal\launch.yaml")
        if exe_path.exists() and src_path.exists():
            cmd = [
                str(exe_path),
                "-src={}".format(src_path),
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
            pane = CPane(window)
            if Path(result).is_dir():
                pane.openPath(result)
            else:
                pyauto.shellExecute(None, result, "", "")
                pane.appendHistory(result)

    window.keymap["Y"] = bind(zyl)

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
                    "-cur={}".format(pane.current_path),
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
                        pyauto.shellExecute(None, result, "", "")
                        pane.appendHistory(result)

            return _func

    window.keymap["Z"] = bind(zyc(False).invoke(-1))
    window.keymap["A-Z"] = bind(zyc(True).invoke(-1))
    window.keymap["S-Z"] = bind(zyc(False).invoke(1))
    window.keymap["A-S-Z"] = bind(zyc(True).invoke(1))
    window.keymap["F"] = bind(zyc(True).invoke(0))

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

    window.keymap["C-S-C"] = bind(smart_copy_name)

    def smart_copy_path():
        pane = CPane(window)
        paths = []
        for i in range(pane.count):
            item = pane.byIndex(i)
            if item.selected():
                paths.append(pane.pathByIndex(i))

        if len(paths) < 1:
            ckit.setClipboardText(pane.current_path)
            print("\ncopied current directory path:\n{}".format(pane.current_path))
            return

        lines = LINE_BREAK.join(paths)
        ckit.setClipboardText(lines)
        print("\ncopied fullpath of items below:")
        for path in paths:
            print("- {}".format(Path(path).name))

    window.keymap["C-A-P"] = bind(smart_copy_path)

    def smart_enter():
        pane = CPane(window)
        if pane.focusedItem.isdir():
            window.command_Enter(None)
        else:
            window.command_Execute(None)

    window.keymap["L"] = bind(smart_enter)
    window.keymap["H"] = window.command_GotoParentDir

    class Selector:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

        @property
        def pane(self) -> CPane:
            return CPane(self._window)

        def allItems(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                pane.select(i)
            pane.repaint(PO.FocusedItems | PO.FocusedHeader)

        def allFiles(self) -> None:
            self.clearAll()
            pane = self.pane
            idx = []
            for i in range(pane.count):
                if not pane.byIndex(i).isdir():
                    pane.select(i)
                    idx.append(i)
            if 0 < len(idx):
                pane.focus(idx[0])
                pane.repaint(PO.FocusedItems | PO.FocusedHeader)

        def allDirs(self) -> None:
            self.clearAll()
            pane = self.pane
            idx = []
            for i in range(pane.count):
                if pane.byIndex(i).isdir():
                    pane.select(i)
                    idx.append(i)
            if 0 < len(idx):
                pane.focus(idx[-1])
                pane.repaint(PO.FocusedItems | PO.FocusedHeader)

        def clearAll(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                pane.unSelect(i)
            pane.repaint(PO.FocusedItems | PO.FocusedHeader)

        def clearFiles(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if pane.byIndex(i).isdir():
                    pane.unSelect(i)
            pane.repaint(PO.FocusedItems | PO.FocusedHeader)

        def clearDirs(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if not pane.byIndex(i).isdir():
                    pane.unSelect(i)
            pane.repaint(PO.FocusedItems | PO.FocusedHeader)

        def byExtension(self, s: str) -> None:
            pane = self.pane
            for i in range(pane.count):
                if Path(pane.pathByIndex(i)).suffix == s:
                    pane.select(i)
            pane.repaint(PO.FocusedItems | PO.FocusedHeader)

        def stemContains(self, s: str) -> None:
            pane = self.pane
            for i in range(pane.count):
                stem = Path(pane.pathByIndex(i)).stem
                if s in stem:
                    pane.select(i)
            pane.repaint(PO.FocusedItems | PO.FocusedHeader)

        def stemStartsWith(self, s: str) -> None:
            pane = self.pane
            for i in range(pane.count):
                stem = Path(pane.pathByIndex(i)).stem
                if stem.startswith(s):
                    pane.select(i)
            pane.repaint(PO.FocusedItems | PO.FocusedHeader)

        def stemEndsWith(self, s: str) -> None:
            pane = self.pane
            for i in range(pane.count):
                stem = Path(pane.pathByIndex(i)).stem
                if stem.endswith(s):
                    pane.select(i)
            pane.repaint(PO.FocusedItems | PO.FocusedHeader)

        def toTop(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if i <= pane.cursor:
                    pane.select(i)
            pane.repaint(PO.FocusedItems | PO.FocusedHeader)

        def toEnd(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if pane.cursor <= i:
                    pane.select(i)
            pane.repaint(PO.FocusedItems | PO.FocusedHeader)

    SELECTOR = Selector(window)

    window.keymap["C-A"] = bind(SELECTOR.allItems)
    window.keymap["C-U"] = bind(SELECTOR.clearAll)
    window.keymap["A-F"] = bind(SELECTOR.allFiles)
    window.keymap["A-S-F"] = bind(SELECTOR.clearDirs)
    window.keymap["A-D"] = bind(SELECTOR.allDirs)
    window.keymap["A-S-D"] = bind(SELECTOR.clearFiles)
    window.keymap["S-Home"] = bind(SELECTOR.toTop)
    window.keymap["S-A"] = bind(SELECTOR.toTop)
    window.keymap["S-End"] = bind(SELECTOR.toEnd)
    window.keymap["S-E"] = bind(SELECTOR.toEnd)

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
    window.keymap["A-J"] = bind(SELECTION_BLOCK.jumpDown)
    window.keymap["A-K"] = bind(SELECTION_BLOCK.jumpUp)

    def duplicate_pane():
        pane = CPane(window, True)
        other = CPane(window, False)
        other.openPath(pane.current_path)
        pane.focusOther()
        other.focus(pane.cursor)

    window.keymap["W"] = bind(duplicate_pane)

    def open_to_other():
        active_pane = CPane(window, True)
        inactive_pane = CPane(window, False)
        inactive_pane.openPath(active_pane.focusItemPath)
        active_pane.focusOther()

    window.keymap["S-L"] = bind(open_to_other)

    def open_parent_to_other():
        active_pane = CPane(window, True)
        parent = str(Path(active_pane.current_path).parent)
        current_name = str(Path(active_pane.current_path).name)
        inactive_pane = CPane(window, False)
        inactive_pane.openPath(parent)
        active_pane.focusOther()
        inactive_pane.focusByName(current_name)

    window.keymap["U"] = bind(open_parent_to_other)

    def on_vscode():
        vscode_path = Path(USER_PROFILE, r"scoop\apps\vscode\current\Code.exe")
        if vscode_path.exists():
            pane = CPane(window)
            pyauto.shellExecute(None, str(vscode_path), pane.current_path, "")

    window.keymap["A-V"] = bind(on_vscode)

    def duplicate_with_name():
        pane = CPane(window)
        focus_path = Path(pane.focusItemPath)
        result = window.commandLine(
            "NewName",
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

    window.keymap["S-D"] = bind(duplicate_with_name)

    window.keymap["A-C"] = window.command_ContextMenu
    window.keymap["A-S-C"] = window.command_ContextMenuDir

    class TextFileMaker:
        def __init__(self, window: MainWindow) -> None:
            self._pane = CPane(window)

        def invoke(self, extension: str = "") -> None:
            def _func() -> None:
                if not hasattr(self._pane.file_list.getLister(), "touch"):
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
                if Path(self._pane.current_path, filename).exists():
                    print("'{}' already exists.".format(filename))
                    return
                self._pane.touch(filename)

            return _func

    TEXT_FILE_MAKER = TextFileMaker(window)

    window.keymap["T"] = bind(TEXT_FILE_MAKER.invoke("txt"))
    window.keymap["M"] = bind(TEXT_FILE_MAKER.invoke("md"))

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

        child_lister = pane.file_list.getLister().getChild(dest_name)
        window._copyMoveCommon(
            pane,
            pane.file_list.getLister(),
            child_lister,
            items,
            "m",
            pane.file_list.getFilter(),
        )
        child_lister.destroy()

    window.keymap["A-O"] = bind(to_obsolete_dir)

    def reload_config():
        window.configure()
        window.command_MoveSeparatorCenter(None)
        LeftPane(window).activate()
        ts = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
        print("{} reloaded config.py\n".format(ts))

    window.keymap["C-R"] = bind(reload_config)
    window.keymap["F5"] = bind(reload_config)

    def open_doc():
        help_path = str(Path(ckit.getAppExePath(), "doc", "index.html"))
        pyauto.shellExecute(None, help_path, "", "")

    window.keymap["A-H"] = bind(open_doc)

    def edit_config():
        dir_path = Path(USER_PROFILE, r"Sync\develop\repo\cfiler")
        if dir_path.exists():
            dp = str(dir_path)
            vscode_path = Path(USER_PROFILE, r"scoop\apps\vscode\current\Code.exe")
            if vscode_path.exists():
                vp = str(vscode_path)
                pyauto.shellExecute(None, vp, dp, "")
            else:
                pyauto.shellExecute(None, dp, "", "")
        else:
            pyauto.shellExecute(None, USER_PROFILE, "", "")
            print("cannot find repo dir. open user profile instead.")

    window.keymap["C-E"] = bind(edit_config)

    window.keymap["C-S-N"] = window.command_Mkdir

    ################################
    ################################
    ################################
    ################################
    ################################

    # https://github.com/crftwr/cfiler/blob/0d1017e93939b53024b9ba80492c428d3ae24b8b/_config.py#L284
    def command_CheckEmpty(_):

        pane = window.activePane()
        location = window.activeFileList().getLocation()
        items = window.activeItems()

        result_items = []
        message = [""]

        def jobCheckEmpty(job_item):

            def printBoth(s):
                print(s)
                message[0] += s + "\n"

            def appendResult(item):
                result_items.append(item)
                printBoth("   %s" % item.getName())

            printBoth("空のディレクトリを検索 :")

            # ビジーインジケータ On
            window.setProgressValue(None)

            for item in items:

                if not item.isdir():
                    continue

                if job_item.isCanceled():
                    break
                if job_item.waitPaused():
                    window.setProgressValue(None)

                empty = True

                for root, dirs, files in item.walk(False):

                    if job_item.isCanceled():
                        break
                    if job_item.waitPaused():
                        window.setProgressValue(None)

                    if not empty:
                        break
                    for file in files:
                        empty = False
                        break

                if empty:
                    appendResult(item)

            message[0] += "\n"
            message[0] += "検索結果をファイルリストに反映しますか？(Enter/Esc):\n"

        def jobCheckEmptyFinished(job_item):

            # ビジーインジケータ Off
            window.clearProgress()

            if job_item.isCanceled():
                print("中断しました.\n")
            else:
                print("Done.\n")

            if job_item.isCanceled():
                return

            result = popResultWindow(window, "検索完了", message[0])
            if not result:
                return

            window.jumpLister(
                pane, lister_Custom(window, "[empty] ", location, result_items)
            )

        job_item = ckit.JobItem(jobCheckEmpty, jobCheckEmptyFinished)
        window.taskEnqueue(job_item, "CheckEmpty")

    # https://github.com/crftwr/cfiler/blob/0d1017e93939b53024b9ba80492c428d3ae24b8b/_config.py#L361
    def command_CheckDuplicate(_):

        left_pane = window.leftPane()
        right_pane = window.rightPane()

        left_location = window.leftFileList().getLocation()
        right_location = window.rightFileList().getLocation()

        left_items = window.leftItems()
        right_items = window.rightItems()

        items = []
        for item in left_items:
            if not item.isdir() and hasattr(item, "getFullpath"):
                items.append([item, None, False])
        for item in right_items:
            if not item.isdir() and hasattr(item, "getFullpath"):
                items.append([item, None, False])

        if len(items) <= 1:
            return

        result_left_items = set()
        result_right_items = set()
        message = [""]

        def jobCheckDuplicate(job_item):

            def printBoth(s):
                print(s)
                message[0] += s + "\n"

            def appendResult(item):
                if item in left_items:
                    result_left_items.add(item)
                    printBoth("   Left: %s" % item.getName())
                else:
                    result_right_items.add(item)
                    printBoth("  Right: %s" % item.getName())

            def leftOrRight(item):
                if item in left_items:
                    return "Left"
                else:
                    return "Right"

            printBoth("重複するファイルを検索 :")

            # ビジーインジケータ On
            window.setProgressValue(None)

            for i, item in enumerate(items):

                if job_item.isCanceled():
                    break
                if job_item.waitPaused():
                    window.setProgressValue(None)

                digest = hashlib.md5(item[0].open().read(64 * 1024)).hexdigest()
                print("MD5 : %s : %s" % (item[0].getName(), digest))
                items[i][1] = digest

            # ファイルサイズとハッシュでソート
            if not job_item.isCanceled():
                items.sort(key=lambda item: (item[0].size(), item[1]))

            for i in range(len(items)):

                if job_item.isCanceled():
                    break
                if job_item.waitPaused():
                    window.setProgressValue(None)

                item1 = items[i]
                if item1[2]:
                    continue

                dumplicate_items = []
                dumplicate_filenames = [item1[0].getFullpath()]

                for k in range(i + 1, len(items)):

                    if job_item.isCanceled():
                        break
                    if job_item.waitPaused():
                        window.setProgressValue(None)

                    item2 = items[k]
                    if item1[1] != item2[1]:
                        break
                    if item2[2]:
                        continue
                    if item2[0].getFullpath() in dumplicate_filenames:
                        item2[2] = True
                        continue

                    print(
                        "比較 : %5s : %s" % (leftOrRight(item1[0]), item1[0].getName())
                    )
                    print(
                        "     : %5s : %s …"
                        % (leftOrRight(item2[0]), item2[0].getName()),
                    )

                    try:
                        result = compareFile(
                            item1[0].getFullpath(),
                            item2[0].getFullpath(),
                            shallow=1,
                            schedule_handler=job_item.isCanceled,
                        )
                    except CanceledError:
                        print("中断")
                        break

                    if result:
                        print("一致")
                        dumplicate_items.append(item2)
                        dumplicate_filenames.append(item2[0].getFullpath())
                        item2[2] = True
                    else:
                        print("不一致")

                    print("")

                if dumplicate_items:
                    appendResult(item1[0])
                    for item2 in dumplicate_items:
                        appendResult(item2[0])
                    printBoth("")

            message[0] += "\n"
            message[0] += "検索結果をファイルリストに反映しますか？(Enter/Esc):\n"

        def jobCheckDuplicateFinished(job_item):

            # ビジーインジケータ Off
            window.clearProgress()

            if job_item.isCanceled():
                print("中断しました.\n")
            else:
                print("Done.\n")

            if job_item.isCanceled():
                return

            result = popResultWindow(window, "検索完了", message[0])
            if not result:
                return

            window.leftJumpLister(
                lister_Custom(
                    window, "[duplicate] ", left_location, list(result_left_items)
                )
            )
            window.rightJumpLister(
                lister_Custom(
                    window, "[duplicate] ", right_location, list(result_right_items)
                )
            )

        job_item = ckit.JobItem(jobCheckDuplicate, jobCheckDuplicateFinished)
        window.taskEnqueue(job_item, "CheckDuplicate")

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
        pyauto.shellExecute(None, str(exe_path), param, "")

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
        pane.repaint(PO.FocusedItems | PO.FocusedHeader)

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
        pane.repaint(PO.FocusedItems | PO.FocusedHeader)

    def select_stem_startswith():
        pass

    def select_stem_endsswith():
        pass

    def select_stem_contains():
        pass

    def select_byext():
        pass

    def update_command_list(command_table: dict) -> None:
        for name, func in command_table.items():
            window.launcher.command_list += [(name, bind(func))]

    update_command_list(
        {
            "Diffinity": diffinity,
            "SelectNameUnique": select_name_unique,
            "SelectNameCommon": select_name_common,
            "SelectStemStartsWith": select_stem_startswith,
            "SelectStemEndsWith": select_stem_endsswith,
            "SelectStemContains": select_stem_contains,
            "SelectByExtension": select_byext,
            "CheckEmpty": command_CheckEmpty,
            "CheckDuplicate": command_CheckDuplicate,
        }
    )


def configure_TextViewer(window: ckit.TextWindow):
    window.keymap["J"] = window.command_ScrollDown
    window.keymap["K"] = window.command_ScrollUp
