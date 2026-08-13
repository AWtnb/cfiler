from __future__ import annotations

from .tools import keybinder
from .tools.rename import extension as rename_ext
from .tools.rename import index as rename_index
from .tools.rename import insert as rename_insert
from .tools.rename import regexp as rename_regexp
from .tools.rename import stem as rename_stem
from .tools.rename import substr as rename_substr


def setup(window) -> None:

    rename_ext.setup(window)
    rename_index.setup(window)
    rename_insert.setup(window)
    rename_regexp.setup(window)
    rename_stem.setup(window)
    rename_substr.setup(window)
    keybinder.setup(window)

    keybinder.bind(rename_ext.execute, "S-N")
    keybinder.bind(rename_index.execute, "A-S-I")
    keybinder.bind(rename_insert.execute, "S-I")
    keybinder.bind(rename_regexp.execute, "S-R")
    keybinder.bind(rename_stem.execute, "N")
    keybinder.bind(rename_substr.execute, "S-S")
