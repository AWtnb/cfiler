from __future__ import annotations

import os
from pathlib import Path

import ckit  # type: ignore

from .. import cpane, kiritori
from . import renamer


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    cpane.setup(window)
    kiritori.setup(window)
    renamer.setup(window)


def execute() -> None:
    pane = cpane.CPane()
    if pane.isBlank:
        return
    item = pane.focusedItem
    if item.isdir():
        return

    if not renamer.is_renamable(item) or pane.isBlank:
        return

    focused_path = Path(item.getFullpath())
    placeholder = focused_path.suffix

    exts = []
    for item in pane.items:
        name = item.getName()
        _, ext = os.path.splitext(name)
        if 0 < len(ext):
            exts.append(ext)
    exts = sorted(set(exts))

    def _listup_exts(
        update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
    ) -> tuple:
        found = []
        for ext in exts:
            if ext.lower().startswith(update_info.text.lower()):
                found.append(ext)
        return found, 0

    new_ext, mod = window.commandLine(
        title="NewExt",
        text=placeholder,
        selection=[1, len(placeholder)],
        candidate_handler=_listup_exts,
        return_modkey=True,
    )

    if new_ext is None:
        new_ext = ""

    new_name = focused_path.stem + new_ext

    kiritori.draw_header("Renaming:")
    renamer.execute(pane, focused_path, new_name, mod == ckit.MODKEY_SHIFT)
    kiritori.draw_footer()
