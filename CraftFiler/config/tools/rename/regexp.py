from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from cfiler_resultwindow import popResultWindow  # type: ignore

from .. import cpane, kiritori
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


INI_OPTION = "regexp"


class RenameParam(NamedTuple):
    pattern: str
    new_str: str
    is_case_sensitive: bool

    def as_command(self) -> str:
        cmd = f"{self.pattern}/{self.new_str}"
        if self.is_case_sensitive:
            cmd += "/c"
        return cmd


def get_param() -> RenameParam | None:
    sep = "/"
    placeholder = sep
    sel_end = 0

    last_regexp = rename_ini.get_value(INI_OPTION)
    if 0 < len(last_regexp):
        placeholder = last_regexp
        sel_end = max(last_regexp.find("/"), sel_end)

    print("Rename with regexp-replace. Trailing `/c` enables case-sensitive-mode")
    rename_command = window.commandLine(
        "[regexp]/[replace with](/c)", text=placeholder, selection=[0, sel_end]
    )

    if not rename_command:
        return None

    elems = rename_command.split(sep)
    base = elems[0]
    if not base:
        return None
    new_str = ""
    if 1 < len(elems):
        new_str = elems[1]

    return RenameParam(
        pattern=base,
        new_str=new_str,
        is_case_sensitive=(2 < len(elems) and elems[2] == "c"),
    )


def execute() -> None:
    pane = cpane.CPane()
    targets = renamer.get_renamable_items(pane)
    if len(targets) < 1:
        return

    param = get_param()
    if param is None:
        return

    rename_command = param.as_command()
    rename_ini.register(INI_OPTION, rename_command)
    reg = (
        re.compile(param.pattern)
        if param.is_case_sensitive
        else re.compile(param.pattern, re.IGNORECASE)
    )

    def _confirm() -> tuple[list[RenameInfo], bool]:
        infos = []
        lines = []
        for item in targets:
            org_path = Path(item.getFullpath())
            new_name = reg.sub(param.new_str, org_path.stem) + org_path.suffix
            if org_path.name != new_name:
                infos.append(RenameInfo(org_path, new_name))
                lines.append(f"Rename: {org_path.name}\n    ==> {new_name}\n")

        if len(lines) < 1:
            lines.append("Nothing will be renamed.")
        else:
            lines.append(
                f"\nregexp: {reg}\nnew text: {param.new_str}\nOK? (Enter / Esc)"
            )

        return infos, popResultWindow(window, "Preview", "\n".join(lines))

    infos, ok = _confirm()
    if len(infos) < 1 or not ok:
        print("Canceled.\n")
        return

    kiritori.draw_header("Renaming:")
    [renamer.execute(pane, info.orgPath, info.newName) for info in infos]
    kiritori.draw_footer()
