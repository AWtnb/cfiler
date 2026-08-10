from __future__ import annotations

import re
from pathlib import Path
from typing import NamedTuple

from .. import cpane
from . import ini as rename_ini
from . import renamer


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    cpane.setup(window)
    renamer.setup(window)
    rename_ini.setup(window)


"""
command:
Index[@position,step,skips1,skips2,...;connector;newstem]
"""


class Index(NamedTuple):
    number: int
    width: int
    pad: str
    position: int
    step: int
    skips: list[int]

    def to_string(self) -> str:
        if len(self.pad) == 1:
            return f"{str(self.number).rjust(self.width, self.pad)}"
        return str(self.number).rjust(self.width)

    def increment(self) -> Index:
        n = self.number + self.step
        while n in self.skips:
            n += self.step
        return self._replace(number=n)


REG_DIGITS = re.compile(r"[0-9]+")


def as_index(s: str) -> Index:
    base, rest = s.split("@", 1)
    base = base.rstrip()
    params = [s.strip() for s in rest.split(",")]

    m = REG_DIGITS.search(base)
    assert m is not None
    index = int(m.group())
    width = len(base)

    first_char = base[0]
    pad = "" if first_char in "123456789" else first_char

    position = -1
    if params[0]:
        position = int(params[0])

    step = 1
    if 1 < len(params) < 2:
        step = int(params[1])

    skips = []
    for i, p in enumerate(params):
        if 1 < i:
            skips.append(int(p))

    return Index(
        number=index,
        width=width,
        pad=pad,
        position=position,
        step=step,
        skips=skips,
    )


class RenameParam(NamedTuple):
    index: Index
    connector: str
    new_stem: str

    def as_command(self) -> str:
        idx = self.index
        skips = ""
        if idx.skips:
            skips += ","
            skips += ",".join([str(s) for s in idx.skips])
        return f"{idx.to_string()}@{idx.position},{idx.step}{skips};{self.connector};{self.new_stem}"


INI_OPTION = "index"


def get_param() -> RenameParam | None:
    last_value = rename_ini.get_value(INI_OPTION)
    placeholder = last_value if 0 < len(last_value) else "01@-1,1;_;"

    print("Rename insert index:")
    rename_command: str | None = window.commandLine(
        "Index[@position,step,skips1,skips2,...;connector;newstem]",
        text=placeholder,
    )

    if rename_command is None or len(rename_command) < 1:
        return None

    sep = ";"
    if sep not in rename_command:
        rename_command += sep * 2
    else:
        if rename_command.count(sep) < 2:
            rename_command += sep

    base, connector, new_stem, *_ = rename_command.split(sep)

    if not REG_DIGITS.search(base):
        return None

    return RenameParam(
        index=as_index(base),
        connector=connector,
        new_stem=new_stem,
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
    print(rename_command)
    rename_ini.register(INI_OPTION, rename_command)

    renames: list[renamer.ItemRename] = []

    idx = param.index
    for item in targets:
        org_path = Path(item.getFullpath())
        stem = org_path.stem
        if param.new_stem:
            stem = param.new_stem
        pos = idx.position
        if pos < 0:
            pos += len(stem) + 1
        new_name = (
            stem[:pos]
            + param.connector
            + idx.to_string()
            + stem[pos:]
            + org_path.suffix
        )
        idx = idx.increment()
        renames.append(renamer.ItemRename(org_path, new_name))

    renamer.execute(pane, renames)
