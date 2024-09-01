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


def print_log(s: str, padding: int = 1) -> None:
    p = "\n" * padding
    print(p + s + p)


def delay(msec: int = 50) -> None:
    time.sleep(msec / 1000)


def configure(window: MainWindow) -> None:

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
            "C-N": window.command_DuplicateCfiler,
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

    def invoke_listwindow(window: MainWindow, prompt: str, items) -> Tuple[str, int]:
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
            initial_select=0,
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
            self._dests = []

        def register(self, dest_table: dict) -> None:
            for name, path in dest_table.items():
                p = Path(path)
                try:
                    if p.exists():
                        self._dests += [(name, str(p))]
                except Exception as e:
                    print_log(e)

        def jump(self) -> None:
            result, mod = invoke_listwindow(self._window, "Jump", self._dests)
            if -1 < result:
                dest = self._dests[result][1]
                active = CPane(self._window, True)
                other = CPane(self._window, False)
                if mod == ckit.MODKEY_SHIFT:
                    other.openPath(dest)
                else:
                    active.openPath(dest)

    JUMP_LIST = JumpList(window)

    JUMP_LIST.register(
        {
            "Desktop": str(Path(USER_PROFILE, "Desktop")),
            "Dropbox": str(Path(USER_PROFILE, "Dropbox")),
            "Dropbox Share": str(
                Path(USER_PROFILE, "Dropbox", "_sharing", "_yuhikaku")
            ),
            "Scan": r"X:\scan",
        }
    )

    KEYBINDER.bind("C-Space", JUMP_LIST.jump)

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

        def toggleSelection(self, i: int) -> None:
            self.fileList.selectItem(i, None)
            self.applySelectionHighlight()

        def setSelectionState(self, i: int, state: bool) -> None:
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

        def openPath(self, path: str) -> None:
            target = Path(path)
            if not target.exists():
                print_log("invalid path: '{}'".format(path))
                return
            focus_name = None
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
                self.focus(self._window.cursorFromName(self.fileList, name))

        def copyToChild(
            self, dest_name: str, items: list, remove_origin: bool = False
        ) -> None:
            if remove_origin:
                mode = "m"
            else:
                mode = "c"
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
        pane.entity.cursor -= 1
        if pane.cursor < 0:
            pane.entity.cursor = pane.count - 1
        pane.scrollToCursor()

    KEYBINDER.bind("K", smart_cursorUp)
    KEYBINDER.bind("Up", smart_cursorUp)

    def smart_cursorDown(_) -> None:
        pane = CPane(window)
        if pane.isBlank or pane.count == 1:
            return
        pane.entity.cursor += 1
        if pane.count - 1 < pane.cursor:
            pane.entity.cursor = 0
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

    class CFilerExtension:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

        @property
        def archiver(self) -> List[str]:
            exts = []
            for archiver in self._window.archiver_list:
                for ext in archiver[0].split():
                    exts.append(ext[1:])
            return exts

        @property
        def image(self) -> List[str]:
            exts = []
            for im in self._window.image_file_ext_list:
                exts.append(im)
            return exts

        @property
        def music(self) -> List[str]:
            exts = []
            for im in self._window.music_file_ext_list:
                exts.append(im)
            return exts

    CFILER_EXTENSION = CFilerExtension(window)

    def hook_enter() -> bool:
        # returning `True` skips default action.

        pane = CPane(window)
        if pane.isBlank:
            return True

        p = pane.focusedItemPath
        ext = Path(p).suffix

        if ext in CFILER_EXTENSION.archiver:
            return True

        if ext in CFILER_EXTENSION.music or ext == ".m4a":
            return shell_exec(p)

        if ext == ".pdf":
            sumatra_path = Path(
                USER_PROFILE, r"AppData\Local\SumatraPDF\SumatraPDF.exe"
            )
            if sumatra_path.exists():
                return shell_exec(str(sumatra_path), p)

        if ext in [".xlsx", ".xls"]:
            excel_path = Path(
                r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Excel.lnk"
            )
            if excel_path.exists():
                return shell_exec(str(excel_path), p)

        if ext in [".docx", ".doc"]:
            word_path = Path(
                r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\Word.lnk"
            )
            if word_path.exists():
                return shell_exec(str(word_path), p)

        if ext in [".pptx", ".ppt"]:
            word_path = Path(
                r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs\PowerPoint.lnk"
            )
            if word_path.exists():
                return shell_exec(str(word_path), p)

        return False

    window.enter_hook = hook_enter

    def smart_enter() -> None:
        pane = CPane(window)
        if pane.isBlank:
            pane.focusOther()
        else:
            if pane.focusedItem.isdir():
                window.command_Enter(None)
            else:
                if Path(pane.focusedItemPath).suffix in CFILER_EXTENSION.archiver:
                    return
                window.command_Execute(None)

    KEYBINDER.bind("L", smart_enter)
    KEYBINDER.bind("Right", smart_enter)

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
        pane = CPane(window, True)
        pane_selects = pane.selectedItemNames
        current_path = pane.currentPath
        other_pane = CPane(window, False)
        other_pane_selects = other_pane.selectedItemNames
        other_path = other_pane.currentPath

        pane.openPath(other_path)
        pane.selectByNames(other_pane_selects)

        other_pane.openPath(current_path)
        other_pane.selectByNames(pane_selects)

        LeftPane(window).activate()

    KEYBINDER.bind("S", swap_pane)

    class DirRule:
        def __init__(self, current_path: str, src_name: str = ".dirnames") -> None:
            self._current_path = current_path
            self._src_name = src_name

        def read_src(self) -> str:
            p = Path(self._current_path)
            depth = len(p.parents) + 1
            for _ in range(depth):
                f = Path(p, self._src_name)
                if f.exists():
                    return f.read_text("utf-8")
                p = p.parent
            return ""

        def fzf(self) -> str:
            src = self.read_src().strip()
            if len(src) < 1:
                print_log("src file '{}' not found...".format(self._src_name))
                return ""
            try:
                proc = subprocess.run(
                    "fzf.exe", input=src, capture_output=True, encoding="utf-8"
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

    KEYBINDER.bind("A-N", ruled_mkdir)

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
            autofix_list=["/", "\\"],
            candidate_handler=candidate_Filename(pane.fileList.getLocation()),
            return_modkey=True,
        )
        if result == None:
            return
        result = result.strip()
        if len(result) < 1:
            return
        open_path = Path(pane.currentPath, result)
        if mod == ckit.MODKEY_SHIFT:
            CPane(window, False).openPath(str(open_path))
            pane.focusOther()
        else:
            pane.openPath(str(open_path))

    KEYBINDER.bind("F", smart_jump_input)

    def smart_extract() -> None:
        active_pane = CPane(window)

        for item in active_pane.selectedItems:
            if Path(item.getFullpath()).suffix not in CFILER_EXTENSION.archiver:
                active_pane.unSelect(active_pane.byName(item.getName()))

        if len(active_pane.selectedItems) < 1:
            return

        out_dir = datetime.datetime.today().strftime("unzip_%Y%m%d%H%M%S")
        active_pane.mkdir(out_dir, False)
        extract_path = str(Path(active_pane.currentPath, out_dir))

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

        @property
        def targets(self) -> list:
            pane = self.pane
            if pane.hasSelection:
                return pane.selectedItems
            return pane.items

        def files(self) -> None:
            pane = self.pane
            for item in self.targets:
                name = item.getName()
                if not item.isdir():
                    pane.toggleSelection(pane.byName(name))

        def dirs(self) -> None:
            pane = self.pane
            for item in self.targets:
                name = item.getName()
                if item.isdir():
                    pane.toggleSelection(pane.byName(name))

        def toTop(self) -> None:
            pane = self.pane
            for item in self.targets:
                name = item.getName()
                idx = pane.byName(name)
                if idx <= pane.cursor:
                    pane.toggleSelection(idx)

        def toEnd(self) -> None:
            pane = self.pane
            for item in self.targets:
                name = item.getName()
                idx = pane.byName(name)
                if pane.cursor <= idx:
                    pane.toggleSelection(idx)

        def clearAll(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                pane.unSelect(i)

        def byFunction(self, func: Callable, negative: bool = False) -> None:
            pane = self.pane
            for item in self.targets:
                path = item.getFullpath()
                if (negative and not func(path)) or (not negative and func(path)):
                    name = item.getName()
                    pane.toggleSelection(pane.byName(name))
            pane.focus(pane.selectionTop)

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
            "U": SELECTOR.clearAll,
            "A-F": SELECTOR.files,
            "A-D": SELECTOR.dirs,
            "S-Home": SELECTOR.toTop,
            "S-A": SELECTOR.toTop,
            "S-End": SELECTOR.toEnd,
            "S-E": SELECTOR.toEnd,
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
        inactive_pane.openPath(parent)
        active_pane.focusOther()
        inactive_pane.focusByName(current_name)

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

    def invoke_renamer(append: Union[bool, None]) -> Callable:
        def _renamer() -> None:
            pane = CPane(window)
            item = pane.focusedItem
            if (
                not hasattr(item, "rename")
                or not hasattr(item, "utime")
                or not hasattr(item, "uattr")
            ):
                return
            org_path = Path(item.getFullpath())
            offset = len(org_path.stem)
            if append is None:
                sel = [0, offset]
            elif append:
                sel = [offset, offset]
            else:
                sel = [0, 0]

            new_name = window.commandLine(
                title="NewName",
                text=org_path.name,
                selection=sel,
            )

            if not new_name:
                return

            new_path = str(org_path.with_name(new_name))

            try:
                window.subThreadCall(org_path.rename, (new_path,))
                print_log("Renamed: {} ==> {}".format(org_path.name, new_name))
                pane.refresh()
                pane.focusByName(new_name)
            except Exception as e:
                print(e)

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
        if remove_origin:
            prompt = "MoveTo"
        else:
            prompt = "CopyTo"

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
                dn = d.getName()
                if not dn in names:
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
                result = window.commandLine(
                    prompt, auto_complete=True, candidate_handler=_listup_files
                )
                if not result:
                    return
                filename = result.strip()
                if len(filename) < 1:
                    return
                if 0 < len(extension):
                    filename = filename + "." + extension
                if Path(pane.currentPath, filename).exists():
                    print_log("'{}' already exists.".format(filename))
                    return
                pane.touch(filename)

            return _func

    TEXT_FILE_MAKER = TextFileMaker(window)

    KEYBINDER.bind("T", TEXT_FILE_MAKER.invoke("txt"))
    KEYBINDER.bind("A-T", TEXT_FILE_MAKER.invoke("md"))
    KEYBINDER.bind("S-T", TEXT_FILE_MAKER.invoke(""))

    def to_obsolete_dir() -> None:
        pane = CPane(window)

        items = []
        for i in range(pane.count):
            item = pane.byIndex(i)
            if item.selected() and hasattr(item, "delete"):
                items.append(item)
        if len(items) < 1:
            return

        dest_name = "_obsolete"
        pane.mkdir(dest_name, False)
        pane.copyToChild(dest_name, items, True)

    KEYBINDER.bind("A-O", to_obsolete_dir)

    Rect = namedtuple("Rect", ["left", "top", "right", "bottom"])

    def adjust_position() -> None:
        hwnd = window.getHWND()
        wnd = pyauto.Window.fromHWND(hwnd)
        rect = Rect(*wnd.getRect())
        infos = pyauto.Window.getMonitorInfo()
        if 1 < len(infos):
            return
        visible_rect = Rect(*infos[0][1])
        if (
            visible_rect.right <= rect.left
            or rect.right <= visible_rect.left
            or rect.bottom <= visible_rect.top
            or visible_rect.bottom <= rect.top
        ):
            if wnd.isMaximized():
                wnd.restore()
            left = (visible_rect.right - visible_rect.left) // 2
            wnd.setRect([left, 0, visible_rect.right, visible_rect.bottom])

    def reload_config() -> None:
        window.configure()
        window.reloadTheme()
        adjust_position()
        window.command_MoveSeparatorCenter(None)
        LeftPane(window).activate()
        ts = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S.%f")
        print_log("{} reloaded config.py".format(ts))

    KEYBINDER.bind("C-R", reload_config)
    KEYBINDER.bind("F5", reload_config)

    def starting_position() -> None:
        desktop_path = str(Path(USER_PROFILE, "Desktop"))
        pane = CPane(window, True)
        if pane.currentPath != desktop_path:
            pane.openPath(desktop_path)
        window.command_ChdirInactivePaneToOther(None)
        window.command_MoveSeparatorCenter(None)
        LeftPane(window).activate()

    KEYBINDER.bind("0", starting_position)

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

        def traverse_inactive_pane(self) -> list:
            paths = []
            for item in self._inactive_pane.items:
                if item.isdir():
                    for _, _, files in item.walk():
                        for file in files:
                            paths.append(file.getFullpath())
                else:
                    paths.append(item.getFullpath())
            return paths

        def compare(self) -> None:
            def _scan(job_item: ckit.JobItem) -> None:
                items = []
                from_selection = self._active_pane.hasSelection

                if from_selection:
                    for item in self._active_pane.selectedItems:
                        if not item.isdir():
                            items.append(item)
                else:
                    items = self._active_pane.files

                job_item.comparable = 0 < len(items)
                if not job_item.comparable:
                    return

                Selector(window, False).clearAll()

                print_log("=== comparing md5 hash ===")

                window.setProgressValue(None)

                table = {}
                for path in self.traverse_inactive_pane():
                    if job_item.isCanceled():
                        return
                    rel = Path(path).relative_to(self._inactive_pane.currentPath)
                    digest = self.to_hash(path)
                    table[digest] = table.get(digest, []) + [str(rel)]

                cloned_items = ClonedItems()
                for file in items:
                    if job_item.isCanceled():
                        return
                    digest = self.to_hash(file.getFullpath())
                    if digest in table:
                        name = file.getName()
                        if not from_selection:
                            self._active_pane.selectByName(name)
                        cloned_items.register(name, table[digest])

                        for n in table[digest]:
                            self._inactive_pane.selectByName(n)

                cloned_items.show()

            def _finish(job_item: ckit.JobItem) -> None:
                window.clearProgress()
                if not job_item.comparable:
                    print_log("Nothing to compare.")
                if job_item.isCanceled():
                    print_log("Canceled.")
                else:
                    print_log("======== finished ========")

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

    def select_name_common() -> None:
        pane = CPane(window)
        inactive = CPane(window, False)

        if pane.hasSelection:
            names = pane.selectedItemNames
            search_pane = inactive
        else:
            names = inactive.names
            search_pane = pane

        for i in range(search_pane.count):
            item = search_pane.byIndex(i)
            if item.getName() in names:
                search_pane.select(i)

    def select_name_unique() -> None:
        pane = CPane(window)
        names = pane.names
        other = CPane(window, False)
        other_names = other.names
        for i in range(pane.count):
            item = pane.byIndex(i)
            pane.setSelectionState(i, item.getName() not in other_names)
        for i in range(other.count):
            item = other.byIndex(i)
            other.setSelectionState(i, item.getName() not in names)

    def select_stem_startswith() -> None:
        result, mod = window.commandLine("StartsWith", return_modkey=True)
        if result:
            SELECTOR.stemStartsWith(result, mod == ckit.MODKEY_SHIFT)

    def select_stem_endswith() -> None:
        result, mod = window.commandLine("EndsWith", return_modkey=True)
        if result:
            SELECTOR.stemEndsWith(result, mod == ckit.MODKEY_SHIFT)

    def select_stem_contains() -> None:
        result, mod = window.commandLine("Contains", return_modkey=True)
        if result:
            SELECTOR.stemContains(result, mod == ckit.MODKEY_SHIFT)

    def select_byext() -> None:

        exts = []
        for item in SELECTOR.targets:
            ext = Path(item.getFullpath()).suffix
            if ext and ext not in exts:
                exts.append(ext)

        if len(exts) < 1:
            return

        exts.sort()
        result, mod = invoke_listwindow(window, "Select Extension", exts)

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
            "SelectNameUnique": select_name_unique,
            "SelectNameCommon": select_name_common,
            "SelectStemStartsWith": select_stem_startswith,
            "SelectStemEndsWith": select_stem_endswith,
            "SelectStemContains": select_stem_contains,
            "SelectByExtension": select_byext,
        }
    )


def configure_ListWindow(window: ckit.TextWindow) -> None:

    def smart_cursorUp(_) -> None:
        window.select -= 1
        if window.select < 0:
            window.select = len(window.items) - 1
        window.scroll_info.makeVisible(
            window.select, window.itemsHeight(), window.scroll_margin
        )
        window.paint()

    def smart_cursorDown(_) -> None:
        window.select += 1
        if len(window.items) - 1 < window.select:
            window.select = 0
        window.scroll_info.makeVisible(
            window.select, window.itemsHeight(), window.scroll_margin
        )
        window.paint()

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

    def to_top(_) -> None:
        window.scroll_info.pos = 0
        window.paint()

    window.keymap["A"] = to_top
    window.keymap["Home"] = to_top

    def to_end(_) -> None:
        window.scroll_info.pos = window._numLines() - 1
        window.paint()

    window.keymap["E"] = to_end
    window.keymap["End"] = to_end

    def open_original(_) -> None:
        path = window.item.getFullpath()
        window.command_Close(None)
        pyauto.shellExecute(None, path, "", "")

    window.keymap["C-Enter"] = open_original

    def copy_content(_) -> None:
        enc = window.encoding.encoding
        if window.encoding.bom:
            enc = enc + "-sig"
        path = window.item.getFullpath()
        content = Path(path).read_text(enc)
        ckit.setClipboardText(content)
        window.command_Close(None)
        print_log(
            "copied content of '{}' in {} encoding.".format(window.item.getName(), enc)
        )

    window.keymap["C-C"] = copy_content


def configure_ImageViewer(window: ckit.TextWindow) -> None:
    window.keymap["F11"] = window.command_ToggleMaximize
    window.keymap["J"] = window.command_CursorDown
    window.keymap["K"] = window.command_CursorUp
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

    def open_original(_) -> None:
        item = window.items[window.cursor]
        path = item.getFullpath()
        window.command_Close(None)
        pyauto.shellExecute(None, path, "", "")

    window.keymap["C-Enter"] = open_original
