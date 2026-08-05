from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, Iterator

import cfiler_debug  # type: ignore
import ckit  # type: ignore
from cfiler_filelist import (  # type: ignore
    FileList,
    item_Default,
    item_Empty,
    lister_Default,
)
from cfiler_mainwindow import MainWindow  # type: ignore

from . import kiritori
from .common import (
    PaintOption,
    smart_check_path,
)
from .protocols import ItemDefaultProtocol, PaneEntityProtocol


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window


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

    def setSorter(self, sorter: Callable[[list[ItemDefaultProtocol]], None]) -> None:
        window.subThreadCall(self.fileList.setSorter, (sorter,))
        self.refresh()

    @property
    def items(self) -> list[ItemDefaultProtocol]:
        if self.isBlank:
            return []
        return self._items

    @property
    def dirs(self) -> list[ItemDefaultProtocol]:
        items = []
        if self.isBlank:
            return items
        for i in range(self.count):
            item = self.byIndex(i)
            if item.isdir():
                items.append(item)
        return items

    @property
    def files(self) -> list[ItemDefaultProtocol]:
        items = []
        if self.isBlank:
            return items
        for i in range(self.count):
            item = self.byIndex(i)
            if not item.isdir():
                items.append(item)
        return items

    @property
    def stems(self) -> list[str]:
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
    def names(self) -> list[str]:
        names = []
        if self.isBlank:
            return names
        for i in range(self.count):
            item = self.byIndex(i)
            names.append(item.getName())
        return names

    @property
    def paths(self) -> list[str]:
        return [os.path.join(self.currentPath, name) for name in self.names]

    @property
    def extensions(self) -> list[str]:
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
    def selectedItems(self) -> list[ItemDefaultProtocol]:
        items = []
        if self.isBlank:
            return items
        for i in range(self.count):
            item = self.byIndex(i)
            if item.selected():
                items.append(item)
        return items

    @property
    def selectedOrAllItems(self) -> list[ItemDefaultProtocol]:
        if self.hasSelection:
            return self.selectedItems
        return self.items

    @property
    def selectedItemPaths(self) -> list[str]:
        return [item.getFullpath() for item in self.selectedItems]

    @property
    def selectedItemNames(self) -> list[str]:
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
        return not self.count - 1 < i

    def toggleSelection(self, i: int, flush: bool = True) -> None:
        if self.isValidIndex(i):
            self.fileList.selectItem(i, None)
            if flush:
                self.applySelectionHighlight()

    def setSelectionState(self, i: int, state: bool, flush: bool) -> None:
        if self.isValidIndex(i):
            self.fileList.selectItem(i, state)
            if flush:
                self.applySelectionHighlight()

    def select(self, i: int, flush: bool = True) -> None:
        self.setSelectionState(i, True, flush)

    def selectAll(self) -> None:
        for i in range(self.count):
            self.select(i, False)
        self.applySelectionHighlight()

    def unSelect(self, i: int, flush: bool = True) -> None:
        self.setSelectionState(i, False, flush)

    def unSelectAll(self) -> None:
        for i in range(self.count):
            self.unSelect(i, False)
        self.applySelectionHighlight()

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

    def openPath(self, path: str, focus_name: None | str = None) -> None:
        if self.currentPath == path and focus_name is not None:
            self.focusByName(focus_name)
            return

        target = Path(path)
        if not smart_check_path(target):
            kiritori.log(f"invalid path: '{path}'")
            return

        if target.is_file():
            self.openPath(str(target.parent), target.name)
            return

        if focus_name is None:

            def _last_focused_name(hist_item: list) -> str | None:
                (
                    dir_path,
                    filename,
                    _,
                    _,
                ) = hist_item
                if dir_path.startswith(path):
                    if dir_path == path:
                        return filename
                    return dir_path[len(path) + 1 :].split(os.sep)[0]
                return None

            for hist_item in self.entity.history.items + self._other.history.items:
                focus_name = _last_focused_name(hist_item)
                if focus_name is not None:
                    break

        lister = lister_Default(window, path)
        window.jumpLister(self.entity, lister, focus_name)

    def touch(self, name: str) -> None:
        if not hasattr(self.lister, "touch"):
            kiritori.log("cannot make file here.")
            return
        dp = Path(self.currentPath, name)
        if smart_check_path(dp) and dp.is_file():
            kiritori.log(f"file '{name}' already exists.")
            return
        window.subThreadCall(self.lister.touch, (name,))
        self.refresh()
        self.focus(window.cursorFromName(self.fileList, name))

    def mkdir(self, name: str, focus: bool = True) -> None:
        if not hasattr(self.lister, "mkdir"):
            kiritori.log("cannot make directory here.")
            return
        dp = Path(self.currentPath, name)
        if smart_check_path(dp) and dp.is_dir():
            kiritori.log(f"directory '{name}' already exists.")
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

            def __call__(self, name) -> ItemDefaultProtocol | None:
                try:
                    item: ItemDefaultProtocol = item_Default(
                        self.root, ckit.joinPath(self.dirname, name)
                    )
                    return item
                except Exception:  # noqa: BLE001
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
                yield from filter(
                    None,
                    map(ent, subdirs),
                )
            yield from filter(None, map(ent, subfiles))


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
