from __future__ import annotations

from pathlib import Path

from .. import cpane
from ..common import stringify
from . import affix_handler, renamer


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    cpane.setup(window)
    renamer.setup(window)
    affix_handler.setup(window)


def execute() -> None:
    pane = cpane.CPane()
    if pane.isBlank:
        return
    item = pane.focusedItem

    if not renamer.is_renamable(item):
        return

    focused_path = Path(item.getFullpath())
    placeholder = focused_path.name if focused_path.is_dir() else focused_path.stem
    offset = len(placeholder)
    sel = [offset, offset]

    new_stem = window.commandLine(
        title="NewStem",
        text=placeholder,
        selection=sel,
        candidate_handler=affix_handler.invoke_suffix_handler(),
    )

    new_stem = stringify(new_stem)
    if len(new_stem) < 1:
        return

    new_name = new_stem
    if not focused_path.is_dir():
        new_name += focused_path.suffix

    rename = renamer.ItemRename(focused_path, new_name)
    renamer.execute(pane, [rename])
