import re
from pathlib import Path
from typing import Callable

import ckit  # type: ignore

from . import cpane, listwindow
from .rename import affix_handler


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    cpane.setup(window)
    affix_handler.setup(window)
    listwindow.setup(window)


def all_items() -> None:
    cpane.CPane().selectAll()


def to_top() -> None:
    pane = cpane.CPane()
    if pane.cursor < pane.selectionTop:
        for i in range(pane.count):
            if i <= pane.cursor:
                pane.select(i, False)
    else:
        for item in pane.selectedOrAllItems:
            i = pane.byName(item.getName())
            if i <= pane.cursor:
                pane.toggleSelection(i, False)
    pane.applySelectionHighlight()


def clear_to_top() -> None:
    pane = cpane.CPane()
    for i in range(pane.count):
        if i <= pane.cursor:
            pane.unSelect(i, False)
    pane.applySelectionHighlight()


def to_bottom() -> None:
    pane = cpane.CPane()
    if pane.selectionBottom < pane.cursor:
        for i in range(pane.count):
            if pane.cursor <= i:
                pane.select(i, False)
    else:
        for item in pane.selectedOrAllItems:
            i = pane.byName(item.getName())
            if pane.cursor <= i:
                pane.toggleSelection(i, False)
    pane.applySelectionHighlight()


def clear_to_bottom() -> None:
    pane = cpane.CPane()
    for i in range(pane.count):
        if pane.cursor < i:
            pane.unSelect(i, False)
    pane.applySelectionHighlight()


def files() -> None:
    pane = cpane.CPane()
    for item in pane.selectedOrAllItems:
        name = item.getName()
        if not item.isdir():
            pane.toggleSelection(pane.byName(name))


def dirs() -> None:
    pane = cpane.CPane()
    for item in pane.selectedOrAllItems:
        name = item.getName()
        if item.isdir():
            pane.toggleSelection(pane.byName(name))


def clear_all() -> None:
    cpane.CPane().unSelectAll()


def by_selector_func(func: Callable[[str], bool], negative: bool = False) -> None:
    pane = cpane.CPane()
    for item in pane.selectedOrAllItems:
        path = item.getFullpath()
        if (negative and not func(path)) or (not negative and func(path)):
            name = item.getName()
            pane.toggleSelection(pane.byName(name))


def by_extension(s: str, negative: bool = False) -> None:
    def _checkPath(path: str) -> bool:
        return Path(path).suffix == s

    by_selector_func(_checkPath, negative)


def stem_contains(s: str, negative: bool = False) -> None:
    def _checkPath(path: str) -> bool:
        return s in Path(path).stem

    by_selector_func(_checkPath, negative)


def stem_starts_with(s: str, negative: bool = False) -> None:
    def _checkPath(path: str) -> bool:
        return Path(path).stem.startswith(s)

    by_selector_func(_checkPath, negative)


def stem_ends_with(s: str, negative: bool = False) -> None:
    def _checkPath(path: str) -> bool:
        return Path(path).stem.endswith(s)

    by_selector_func(_checkPath, negative)


def stem_matches(s: str, case: bool, negative: bool = False) -> None:
    reg = re.compile(s) if case else re.compile(s, re.IGNORECASE)

    def _checkPath(path: str) -> bool:
        return reg.search(Path(path).stem) is not None

    by_selector_func(_checkPath, negative)


def from_other_names() -> None:
    pane = cpane.CPane()
    pane.unSelectAll()
    active_names = pane.names
    other = cpane.CPane(False)
    other_names = [item.getName() for item in other.selectedOrAllItems]
    for name in active_names:
        if name in other_names:
            pane.selectByName(name)


def from_active_names() -> None:
    pane = cpane.CPane()
    active_names = [item.getName() for item in pane.selectedOrAllItems]
    other = cpane.CPane(False)
    other.unSelectAll()
    other_names = other.names
    for name in other_names:
        if name in active_names:
            other.selectByName(name)


def select_same_name() -> None:
    pane = cpane.CPane()
    active_names = pane.selectedItemNames
    if len(active_names) < 1:
        active_names = [pane.focusedItem.getName()]
    other = cpane.CPane(False)
    other.unSelectAll()

    for name in other.names:
        if name in active_names:
            other.selectByName(name)


def select_name_common() -> None:
    pane = cpane.CPane()
    pane.unSelectAll()
    active_names = pane.names
    other = cpane.CPane(False)
    other.unSelectAll()
    other_names = other.names

    for name in active_names:
        if name in other_names:
            pane.selectByName(name)
    for name in other_names:
        if name in active_names:
            other.selectByName(name)


def select_name_unique() -> None:
    pane = cpane.CPane()
    pane.unSelectAll()
    active_names = pane.names
    other = cpane.CPane(False)
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
        candidate_handler=affix_handler.invoke_prefix_handler(),
    )
    if result:
        stem_starts_with(result, mod == ckit.MODKEY_SHIFT)


def select_regexp(case: bool) -> None:
    result, mod = window.commandLine("Regexp", return_modkey=True)
    if result:
        stem_matches(result, case, mod == ckit.MODKEY_SHIFT)


def select_stem_endswith() -> None:
    result, mod = window.commandLine(
        "EndsWith",
        return_modkey=True,
        candidate_handler=affix_handler.invoke_suffix_handler(),
    )
    if result:
        stem_ends_with(result, mod == ckit.MODKEY_SHIFT)


def select_stem_contains() -> None:
    result, mod = window.commandLine("Contains", return_modkey=True)
    if result:
        stem_contains(result, mod == ckit.MODKEY_SHIFT)


def select_byext() -> None:
    pane = cpane.CPane()
    exts = []
    for item in pane.selectedOrAllItems:
        ext = Path(item.getFullpath()).suffix[1:]
        if ext and ext not in exts:
            exts.append(ext)

    if len(exts) < 1:
        return

    result, mod = listwindow.invoke("Select Extension", exts)

    if result < 0:
        return

    by_extension("." + exts[result], mod == ckit.MODKEY_SHIFT)


def select_empty_dir() -> None:
    pane = cpane.CPane()
    for d in pane.dirs:
        path = Path(d.getFullpath())
        if not any(path.iterdir()):
            pane.selectByName(path.name)


def unselect_panes() -> None:
    cpane.CPane().unSelectAll()
    cpane.CPane(False).unSelectAll()
