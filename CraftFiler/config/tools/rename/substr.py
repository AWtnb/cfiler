from __future__ import annotations

from pathlib import Path

from .. import cpane, kiritori
from . import ini as rename_ini
from . import renamer


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    cpane.setup(window)
    kiritori.setup(window)
    renamer.setup(window)
    rename_ini.setup(window)


def get_new_stem(stem: str, offset: int, length: int) -> str:
    if length < 0:
        if length == -1:
            return stem[offset:]
        return stem[offset : length + 1]
    return stem[offset : offset + length]


INI_OPTION = "substr"


def get_param() -> tuple[int, int] | None:
    placeholder = ";-1"
    sel_end = 0

    if 0 < len(last := rename_ini.get_value(INI_OPTION)):
        placeholder = last
        sel_end = last.find(";")

    print("Rename substring (extract part of filename):")
    rename_command = window.commandLine(
        "Offset[;Length]", text=placeholder, selection=[0, sel_end]
    )

    if rename_command is None or len(rename_command.strip()) < 1:
        return None

    sep = ";"
    if sep not in rename_command:
        rename_command += ";-1"
    else:
        if rename_command.startswith(sep):
            rename_command = "0" + rename_command

    elems = rename_command.split(sep)
    offset = int(elems[0])
    length = int(elems.pop())
    return offset, length


def execute() -> None:
    pane = cpane.CPane()
    targets = renamer.get_renamable_items(pane)
    if len(targets) < 1:
        return

    param = get_param()
    if param is None:
        print("Canceled.\n")
        return

    offset, length = param
    if offset == 0 and length == -1:
        print("Canceled.\n")
        return

    history = f"{offset};{length}"
    rename_ini.register(INI_OPTION, history)

    renames: list[renamer.ItemRename] = []

    for item in targets:
        org_path = Path(item.getFullpath())
        new_name = get_new_stem(org_path.stem, offset, length) + org_path.suffix
        renames.append(renamer.ItemRename(org_path, new_name))

    renamer.execute(pane, renames)
