from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

from cfiler_resultwindow import popResultWindow  # type: ignore

from .. import cpane, kiritori


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    cpane.setup(window)
    kiritori.setup(window)


class ItemRename(NamedTuple):
    org_path: Path
    new_name: str

    def get_preview(self) -> str:
        return f"Rename: {self.org_path.name}\n    ==> {self.new_name}\n"

    def get_result(self) -> str:
        return f"Renamed: {self.org_path.name}\n     ==> {self.new_name}\n"


def is_renamable(item) -> bool:
    return hasattr(item, "rename") and hasattr(item, "utime") and hasattr(item, "uattr")


def get_renamable_items(pane: cpane.CPane) -> list:
    if pane.hasSelection:
        return [item for item in pane.selectedItems if is_renamable(item)]
    item = pane.focusedItem
    if is_renamable(item):
        return [item]
    return []


def execute(pane: cpane.CPane, renames: list[ItemRename]) -> None:
    if len(renames) < 1:
        return

    preview_lines = [r.get_preview() for r in renames]
    preview_lines.append("\nOK? (Enter / Esc)")
    if not popResultWindow(window, "Preview", "\n".join(preview_lines)):
        return

    kiritori.draw_header("Renaming:")
    for rename in renames:
        new_path = rename.org_path.with_name(rename.new_name)
        if new_path.name in [item.name for item in new_path.parent.iterdir()]:
            print(f"'{rename.new_name}' already exists!")
            return
        try:
            window.subThreadCall(rename.org_path.rename, (str(new_path),))
            print(rename.get_result())
            pane.refresh()
        except Exception as e:  # noqa: BLE001
            print(e)
    kiritori.draw_footer()

    last = renames.pop()
    pane.focusByName(last.new_name)
