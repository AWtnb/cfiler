from __future__ import annotations

from pathlib import Path

from .. import cpane
from . import ini as rename_ini
from . import renamer


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    cpane.setup(window)
    renamer.setup(window)
    rename_ini.setup(window)


def get_new_stem(stem: str, ins: str, pos: int) -> str:
    if pos < 0:
        if pos == -1:
            return stem + ins
        p = pos + 1
        return stem[:p] + ins + stem[p:]
    return stem[:pos] + ins + stem[pos:]


INI_OPTION = "insert"


def get_param() -> tuple[str, int] | None:
    sep = "@"
    placeholder = "@-1"
    sel_end = 0

    if 0 < len(last := rename_ini.get_value(INI_OPTION)):
        placeholder = last
        sel_end = last.find(sep)

    print("Rename insert:")
    rename_command = window.commandLine(
        "Text[@position]", text=placeholder, selection=[0, sel_end]
    )

    if rename_command is None or len(rename_command.rstrip()) < 1:
        return None

    if rename_command.startswith(sep) or rename_command.endswith(sep):
        return None

    if sep not in rename_command:
        rename_command += "@-1"

    elems = rename_command.split(sep)
    insert_str = elems[0]
    pos = int(elems.pop())
    return insert_str, pos


def execute() -> None:
    pane = cpane.CPane()
    targets = renamer.get_renamable_items(pane)
    if len(targets) < 1:
        return

    param = get_param()
    if param is None:
        print("Canceled.\n")
        return

    ins, pos = param
    history = f"{ins};{pos}"
    rename_ini.register(INI_OPTION, history)

    renames: list[renamer.ItemRename] = []

    for item in targets:
        org_path = Path(item.getFullpath())

        new_name = get_new_stem(org_path.stem, ins, pos) + org_path.suffix
        renames.append(renamer.ItemRename(org_path, new_name))

    renamer.execute(pane, renames)
