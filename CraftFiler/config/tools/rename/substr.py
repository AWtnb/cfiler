from __future__ import annotations

from pathlib import Path

from cfiler_resultwindow import popResultWindow  # type: ignore

from .. import cpane, kiritori
from ..common import stringify
from ..cpane import CPane
from . import ini as rename_ini
from . import renamer
from .renamer import RenameInfo


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


def get_param() -> tuple[int, int]:
    placeholder = ";-1"
    sel_end = 0

    if 0 < len(last := rename_ini.get_value(INI_OPTION)):
        placeholder = last
        sel_end = last.find(";")

    print("Rename substring (extract part of filename):")
    rename_command = stringify(
        window.commandLine("Offset[;Length]", text=placeholder, selection=[0, sel_end])
    )

    if len(rename_command) < 1:
        print("Canceled.\n")
        return 0, -1

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
    pane = CPane()
    targets = renamer.get_renamable_items(pane)
    if len(targets) < 1:
        return

    offset, length = get_param()
    if offset == 0 and length == -1:
        print("Canceled.\n")
        return

    history = f"{offset};{length}"
    rename_ini.register(INI_OPTION, history)

    def _confirm() -> tuple[list[RenameInfo], bool]:
        infos = []
        lines = []
        for item in targets:
            org_path = Path(item.getFullpath())
            new_name = get_new_stem(org_path.stem, offset, length) + org_path.suffix
            infos.append(RenameInfo(org_path, new_name))
            lines.append(f"Rename: {org_path.name}\n    ==> {new_name}\n")

        lines.append(f"\noffset: {offset}\nlength: {length}\nOK? (Enter / Esc)")

        return infos, popResultWindow(window, "Preview", "\n".join(lines))

    infos, ok = _confirm()
    if len(infos) < 1 or not ok:
        print("Canceled.\n")
        return

    kiritori.draw_header("Renaming:")
    [renamer.execute(pane, info.orgPath, info.newName) for info in infos]
    kiritori.draw_footer()
