import datetime
import hashlib
import inspect
import os
import re
import shutil
import subprocess
import unicodedata

from collections import namedtuple
from pathlib import Path
from typing import List, Callable

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


def configure(window: MainWindow) -> None:

    def reset_default_keys(keys: list) -> None:
        for key in keys:
            window.keymap[key] = lambda _: None

    reset_default_keys(
        [
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
            "N": window.command_Rename,
            "A-C-H": window.command_JumpHistory,
            "Back": window.command_JumpHistory,
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
            "C-N": window.command_DuplicateCfiler,
            "C-Up": window.command_CursorUpSelectedOrBookmark,
            "C-K": window.command_CursorUpSelectedOrBookmark,
            "C-Down": window.command_CursorDownSelectedOrBookmark,
            "C-J": window.command_CursorDownSelectedOrBookmark,
            "A-M": window.command_MoveInput,
            "C-C": window.command_SetClipboard_Fullpath,
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

        def bindmulti(self, mapping: dict) -> None:
            for key, func in mapping.items():
                self._window.keymap[key] = self.wrap(func)

    KEYBINDER = Keybinder(window)

    class JumpList:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

        def update(self, jump_table: dict) -> None:
            for name, path in jump_table.items():
                p = Path(path)
                try:
                    if p.exists():
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
            active = CPane(wnd, True)
            other = CPane(wnd, False)
            if mod == ckit.MODKEY_SHIFT:
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

    KEYBINDER.bind("C-Space", JUMP_LIST.jump)

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
            self._window.subThreadCall(self.fileList.refresh, ())
            self.fileList.applyItems()

        @property
        def items(self) -> list:
            return self._items

        @property
        def dirs(self) -> list:
            items = []
            for i in range(self.count):
                item = self.byIndex(i)
                if item.isdir():
                    items.append(item)
            return items

        @property
        def files(self) -> list:
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
            lister = self.lister
            visible = isinstance(lister, lister_Default)
            return self._pane.history.append(str(p.parent), p.name, visible, False)

        @property
        def cursor(self) -> int:
            return self._pane.cursor

        def focus(self, i: int) -> None:
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
        def selectedOrFocusedItems(self) -> list:
            items = []
            for i in range(self.count):
                item = self.byIndex(i)
                if item.selected():
                    items.append(item)
            if len(items) < 1:
                items.append(self.focusedItem)
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
        def focusedItemPath(self) -> str:
            return self.pathByIndex(self.cursor)

        def displaySelection(self) -> None:
            self.repaint(PO.Upper)

        def toggleSelect(self, i: int) -> None:
            self.fileList.selectItem(i, None)
            self.displaySelection()

        def select(self, i: int) -> None:
            self.fileList.selectItem(i, True)
            self.displaySelection()

        def unSelect(self, i: int) -> None:
            self.fileList.selectItem(i, False)
            self.displaySelection()

        def selectByName(self, name: str) -> None:
            i = self.byName(name)
            if i < 0:
                return
            self.select(i)
            self.displaySelection()

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

        def openPath(self, path: str):
            target = Path(path)
            if not target.exists():
                print("invalid path: '{}'".format(path))
                return
            focus_name = None
            if target.is_file():
                path = str(target.parent)
                focus_name = target.name
            lister = lister_Default(self._window, path)
            self._window.jumpLister(self._pane, lister, focus_name)

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

        def mkdir(self, name: str, focus: bool = True) -> None:
            if not hasattr(self.lister, "mkdir"):
                print("cannot make directory here.")
                return
            dp = Path(self.currentPath, name)
            if dp.exists() and dp.is_dir():
                print("directory '{}' already exists.".format(name))
                return
            self._window.subThreadCall(self.lister.mkdir, (name, None))
            self.refresh()
            if focus:
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

    def shell_exec(path: str, *args) -> bool:
        if type(path) is not str:
            path = str(path)
        if not Path(path).exists():
            print("invalid path: '{}'".format(path))
            return False
        params = []
        for arg in args:
            if len(arg.strip()):
                if " " in arg:
                    params.append('"{}"'.format(arg))
                else:
                    params.append(arg)
        pyauto.shellExecute(None, path, " ".join(params), "")
        return True

    def hook_enter() -> None:
        pane = CPane(window)
        p = pane.focusedItem.getFullpath()
        ext = Path(p).suffix

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
        current_path = pane.currentPath
        other_pane = CPane(window, False)
        other_path = other_pane.currentPath
        pane.openPath(other_path)
        other_pane.openPath(current_path)
        LeftPane(window).activate()

    KEYBINDER.bind("A-S", swap_pane)

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
            print("src file '{}' not found...".format(self._src_name))
            return ""

        def fzf(self) -> str:
            src = self.read_src().strip()
            if len(src) < 1:
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

    def ruled_mkdir():
        pane = CPane(window)
        dr = DirRule(pane.currentPath)
        name = dr.get_name()
        if 0 < len(name):
            pane.mkdir(name)

    KEYBINDER.bind("A-N", ruled_mkdir)

    class zyl:
        def __init__(self, search_all: bool = False) -> None:
            self._exe_path = Path(USER_PROFILE, r"Personal\tools\bin\zyl.exe")
            self._src_path = Path(USER_PROFILE, r"Personal\launch.yaml")
            self._cmd = [
                str(self._exe_path),
                "-src={}".format(self._src_path),
                "-all={}".format(search_all),
                "-exclude=_obsolete,node_modules",
                "-stdout=True",
            ]

        def check(self) -> bool:
            return self._exe_path.exists() and self._src_path.exists()

        def invoke(self) -> Callable:
            def _func() -> None:
                if not self.check():
                    return
                proc = subprocess.run(self._cmd, capture_output=True, encoding="utf-8")
                result = proc.stdout.strip()
                if result:
                    if proc.returncode != 0:
                        if result:
                            print(result)
                        return
                    pane = CPane(window)
                    pane.openPath(result)

            return _func

    KEYBINDER.bindmulti(
        {
            "Z": zyl(False).invoke(),
            "A-Z": zyl(True).invoke(),
        }
    )

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
                proc = subprocess.run(cmd, capture_output=True, encoding="utf-8")
                result = proc.stdout.strip()
                if result:
                    if proc.returncode != 0:
                        if result:
                            print(result)
                        return
                    pane = CPane(window)
                    pane.openPath(result)

            return _func

    KEYBINDER.bindmulti(
        {
            "Y": zyc(False).invoke(-1),
            "A-Y": zyc(True).invoke(-1),
            "S-Y": zyc(False).invoke(1),
            "A-S-Y": zyc(True).invoke(1),
            "S-F": zyc(False).invoke(0),
            "C-F": zyc(True).invoke(0),
        }
    )

    def smart_jump_input():
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
        if not open_path.exists():
            print("invalid-path!")
            return
        if mod == ckit.MODKEY_SHIFT:
            CPane(window, False).openPath(str(open_path))
            pane.focusOther()
        else:
            pane.openPath(str(open_path))

    KEYBINDER.bind("F", smart_jump_input)

    def smart_extract():
        active_pane = CPane(window)
        if len(active_pane.selectedItems) < 1:
            return

        extractable = True
        for p in active_pane.selectedItemPaths:
            if Path(p).suffix != ".zip":
                extractable = False

        if extractable:
            outdir = datetime.datetime.today().strftime("unzip_%Y%m%d%H%M%S")
            active_pane.mkdir(outdir, False)
            inactive_pane = CPane(window, False)
            inactive_pane.openPath(str(Path(active_pane.currentPath, outdir)))
            window.command_ExtractArchive(None)
            active_pane.focusOther()

    KEYBINDER.bind("A-S-T", smart_extract)

    def recylcebin():
        pyauto.shellExecute(None, "shell:RecycleBinFolder", "", "")

    KEYBINDER.bind("C-Z ", recylcebin)

    def copy_current_path():
        pane = CPane(window)
        p = pane.currentPath
        ckit.setClipboardText(p)
        window.setStatusMessage("copied current path: '{}'".format(p), 3000)

    KEYBINDER.bind("C-A-P", copy_current_path)

    def copy_name():
        pane = CPane(window)
        if pane.isBlank:
            return
        items = pane.selectedOrFocusedItems
        names = [item.getName() for item in items]
        ckit.setClipboardText(LINE_BREAK.join(names))
        window.setStatusMessage("copied name (with extension)", 3000)

    KEYBINDER.bind("C-S-C", copy_name)

    def copy_basename():
        pane = CPane(window)
        if pane.isBlank:
            return
        items = pane.selectedOrFocusedItems
        basenames = []
        for item in items:
            p = Path(item.getFullpath())
            basenames.append(p.stem)
        ckit.setClipboardText(LINE_BREAK.join(basenames))
        window.setStatusMessage("copied name (without extension)", 3000)

    KEYBINDER.bind("C-S-B", copy_basename)

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

        def byFunction(self, func: Callable, unselect: bool = False) -> None:
            pane = self.pane
            if not unselect:
                self.clearAll()
            idx = []
            for i in range(pane.count):
                path = pane.pathByIndex(i)
                if func(path):
                    if unselect:
                        pane.unSelect(i)
                    else:
                        pane.select(i)
                        idx.append(i)
            if not unselect and 0 < len(idx):
                pane.focus(idx[0])

        def byExtension(self, s: str, unselect: bool = False) -> None:
            def _checkPath(path: str) -> bool:
                return Path(path).suffix == s

            self.byFunction(_checkPath, unselect)

        def stemContains(self, s: str, unselect: bool = False) -> None:
            def _checkPath(path: str) -> bool:
                return s in Path(path).stem

            self.byFunction(_checkPath, unselect)

        def stemStartsWith(self, s: str, unselect: bool = False) -> None:
            def _checkPath(path: str) -> bool:
                return Path(path).stem.startswith(s)

            self.byFunction(_checkPath, unselect)

        def stemEndsWith(self, s: str, unselect: bool = False) -> None:
            def _checkPath(path: str) -> bool:
                return Path(path).stem.endswith(s)

            self.byFunction(_checkPath, unselect)

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

    KEYBINDER.bindmulti(
        {
            "C-A": SELECTOR.allItems,
            "U": SELECTOR.clearAll,
            "A-F": SELECTOR.allFiles,
            "A-S-F": SELECTOR.clearDirs,
            "A-D": SELECTOR.allDirs,
            "A-S-D": SELECTOR.clearFiles,
            "S-Home": SELECTOR.toTop,
            "S-A": SELECTOR.toTop,
            "S-End": SELECTOR.toEnd,
            "S-E": SELECTOR.toEnd,
        }
    )

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

    def duplicate_pane():
        window.command_ChdirInactivePaneToOther(None)
        pane = CPane(window)
        pane.focusOther()

    KEYBINDER.bind("W", duplicate_pane)

    def open_on_explorer():
        pane = CPane(window, True)
        shell_exec(pane.currentPath)

    KEYBINDER.bind("C-S-E", open_on_explorer)

    def open_to_other():
        active_pane = CPane(window, True)
        inactive_pane = CPane(window, False)
        inactive_pane.openPath(active_pane.focusedItemPath)
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

    KEYBINDER.bind("S-U", open_parent_to_other)

    def on_pdf_xchange_editor():
        xchange_path = r"C:\Program Files\Tracker Software\PDF Editor\PDFXEdit.exe"
        if Path(xchange_path).exists():
            pane = CPane(window)
            paths = pane.selectedItemPaths
            if len(paths) < 1:
                paths.append(pane.focusedItemPath)
            for path in paths:
                if Path(path).suffix == ".pdf":
                    shell_exec(xchange_path, path)

    KEYBINDER.bind("C-P", on_pdf_xchange_editor)

    def on_vscode():
        vscode_path = Path(USER_PROFILE, r"scoop\apps\vscode\current\Code.exe")
        if vscode_path.exists():
            pane = CPane(window)
            shell_exec(str(vscode_path), pane.currentPath)

    KEYBINDER.bind("V", on_vscode)

    def unstoppable_copy(src_path: str, new_path: str) -> None:
        pane = CPane(window)

        def _copy(_) -> None:
            s = Path(src_path)
            if s.is_dir():
                shutil.copytree(src_path, new_path)
            else:
                shutil.copy(src_path, new_path)

        def _finished(_) -> None:
            pane.refresh()
            pane.focusByName(Path(new_path).name)

        job = ckit.JobItem(_copy, _finished)
        window.taskEnqueue(job, create_new_queue=False)

    def duplicate_file():
        pane = CPane(window)
        src_path = Path(pane.focusedItemPath)
        result = window.commandLine(
            title="NewName",
            text=src_path.name,
            selection=[len(src_path.stem), len(src_path.stem)],
        )

        if result:
            result = result.strip()
            if len(result) < 1:
                return
            new_path = src_path.with_name(result)
            if new_path.exists():
                print("same item exists!")
                return
            unstoppable_copy(str(src_path), new_path)

    KEYBINDER.bind("S-D", duplicate_file)

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
    KEYBINDER.bind("A-T", TEXT_FILE_MAKER.invoke("md"))
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
        pane.mkdir(dest_name, False)

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
        shell_exec(help_path)

    KEYBINDER.bind("A-H", open_doc)

    def edit_config():
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
            print("cannot find repo dir. open user profile instead.")

    KEYBINDER.bind("C-E", edit_config)

    ClonedItem = namedtuple("ClonedItem", ["origin", "clones"])

    class ClonedItems:
        _items: List[ClonedItem]

        def __init__(self) -> None:
            self._items = []

        def register(self, item: ClonedItem) -> None:
            self._items.append(item)

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
            return hashlib.md5(open(path, "rb").read(64 * 1024)).hexdigest()

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
                Selector(window, True).clearAll()
                Selector(window, False).clearAll()

                print("\n------------------")
                print(" compare md5 hash ")
                print("------------------\n")

                window.setProgressValue(None)

                table = {}
                for path in self.traverse_inactive_pane():
                    if job_item.isCanceled():
                        return
                    rel = Path(path).relative_to(self._inactive_pane.currentPath)
                    digest = self.to_hash(path)
                    table[digest] = table.get(digest, []) + [str(rel)]

                cloned_items = ClonedItems()
                for file in self._active_pane.files:
                    if job_item.isCanceled():
                        return
                    digest = self.to_hash(file.getFullpath())
                    if digest in table:
                        name = file.getName()
                        self._active_pane.selectByName(name)
                        c = ClonedItem(name, table[digest])
                        cloned_items.register(c)

                        for n in table[digest]:
                            self._inactive_pane.selectByName(n)

                cloned_items.show()

            def _finish(job_item: ckit.JobItem) -> None:
                window.clearProgress()
                if job_item.isCanceled():
                    print("Canceled.\n")
                else:
                    print("\n------------------")
                    print("     FINISHED     ")
                    print("------------------\n")

            job = ckit.JobItem(_scan, _finish)
            window.taskEnqueue(job, create_new_queue=False)

    def compare_file_hash():
        pd = PaneDiff()
        pd.compare()

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
        shell_exec(exe_path, param)

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
        result, mod = window.commandLine("StartsWith", return_modkey=True)
        if result:
            SELECTOR.stemStartsWith(result, mod == ckit.MODKEY_SHIFT)

    def select_stem_endswith():
        result, mod = window.commandLine("EndsWith", return_modkey=True)
        if result:
            SELECTOR.stemEndsWith(result, mod == ckit.MODKEY_SHIFT)

    def select_stem_contains():
        result, mod = window.commandLine("Contains", return_modkey=True)
        if result:
            SELECTOR.stemContains(result, mod == ckit.MODKEY_SHIFT)

    def select_byext():
        pane = CPane(window)
        exts = pane.extensions
        if len(exts) < 1:
            return

        exts.sort()
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
            title="Select Extension",
            items=exts,
            initial_select=0,
            onekey_search=True,
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

        if result < 0:
            return

        ext = "." + exts[result]
        SELECTOR.byExtension(ext, mod == ckit.MODKEY_SHIFT)

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

    def update_command_list(command_table: dict) -> None:
        for name, func in command_table.items():
            window.launcher.command_list += [(name, Keybinder.wrap(func))]

    update_command_list(
        {
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


def configure_TextViewer(window: ckit.TextWindow) -> None:
    window.keymap["J"] = window.command_ScrollDown
    window.keymap["K"] = window.command_ScrollUp
    window.keymap["C-Comma"] = window.command_ConfigMenu

    def open_original(_) -> None:
        path = window.item.getFullpath()
        window.command_Close(None)
        pyauto.shellExecute(None, path, "", "")

    window.keymap["O"] = open_original

    def copy_content(_) -> None:
        enc = window.encoding.encoding
        if window.encoding.bom:
            enc = enc + "-sig"
        path = window.item.getFullpath()
        content = Path(path).read_text(enc)
        ckit.setClipboardText(content)
        window.command_Close(None)
        print(
            "decode '{}' and copied content decoded in {}.\n".format(
                window.item.getName(), enc
            )
        )

    window.keymap["C-C"] = copy_content


def configure_ListWindow(window: ckit.TextWindow) -> None:
    window.keymap["J"] = window.command_CursorDown
    window.keymap["K"] = window.command_CursorUp
    window.keymap["C-J"] = window.command_CursorDownMark
    window.keymap["C-K"] = window.command_CursorUpMark
    for mod in ["", "S-"]:
        window.keymap[mod + "Space"] = window.command_Enter


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

    def open_original(_) -> None:
        item = window.items[window.cursor]
        path = item.getFullpath()
        window.command_Close(None)
        pyauto.shellExecute(None, path, "", "")

    window.keymap["C-O"] = open_original
