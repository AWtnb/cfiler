from pathlib import Path
from typing import NamedTuple

from .. import cpane
from ..cpane import CPane


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    cpane.setup(window)


class RenameInfo(NamedTuple):
    orgPath: Path
    newName: str


def is_renamable(item) -> bool:
    return hasattr(item, "rename") and hasattr(item, "utime") and hasattr(item, "uattr")


def get_renamable_items(pane: CPane) -> list:
    if pane.hasSelection:
        return [item for item in pane.selectedItems if is_renamable(item)]
    item = pane.focusedItem
    if is_renamable(item):
        return [item]
    return []


def execute(pane, org_path: Path, new_name: str, focus: bool = False) -> None:
    new_path = org_path.with_name(new_name)
    if new_path.name in [item.name for item in new_path.parent.iterdir()]:
        print(f"'{new_name}' already exists!")
        return
    try:
        window.subThreadCall(org_path.rename, (str(new_path),))
        print(f"Renamed: {org_path.name}\n     ==> {new_name}\n")
        pane.refresh()
        if focus:
            pane.focusByName(new_name)
    except Exception as e:  # noqa: BLE001
        print(e)
