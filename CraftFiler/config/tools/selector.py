import re
from pathlib import Path
from typing import Callable

from . import cpane


def setup(window) -> None:
    cpane.setup(window)


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
