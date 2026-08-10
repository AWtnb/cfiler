from __future__ import annotations

import os
from pathlib import Path

from cfiler_filelist import filter_Default  # type: ignore

from . import cpane
from .common import PaintOption


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    cpane.setup(window)


class PathMatchFilter:
    def __init__(self, root: str, names: list[str]) -> None:
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
        return f"\U0001f50d[{Path(self.root).name}]"


def hide_unselected() -> None:
    pane = cpane.CPane()
    if pane.hasSelection:
        names = pane.selectedItemNames
        window.subThreadCall(
            pane.fileList.setFilter, (PathMatchFilter(pane.currentPath, names),)
        )
        pane.refresh()
        pane.focus(0)
        pane.repaint(PaintOption.Focused)
        cpane.CPane().unSelectAll()


def clear_filter() -> None:
    pane = cpane.CPane()
    window.subThreadCall(pane.fileList.setFilter, (filter_Default("*"),))
    pane.refresh()
    pane.repaint(PaintOption.Focused)
