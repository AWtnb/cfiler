import re
from pathlib import Path

from .. import cpane
from . import renamer


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    cpane.setup(window)
    renamer.setup(window)


VOICABLES = (
    "かきくけこさしすせそたちつてとはひふへほカキクケコサシスセソタチツテトハヒフヘホ"
)


def fix(s: str, offset: int) -> str:
    c = s[0]
    if c not in VOICABLES:
        return s
    if offset == 1:
        if c == "う":
            return "\u3094"
        if c == "ウ":
            return "\u30f4"
    return chr(ord(c) + offset)


REG_PSEUDO_VOICING = re.compile(r".[\u309b\u3099]")
REG_PSEUDO_HALF_VOICING = re.compile(r".[\u309a\u309c]")


def fix_voicing(s: str) -> str:
    return REG_PSEUDO_VOICING.sub(lambda m: fix(m.group(), 1), s)


def fix_half_voicing(s: str) -> str:
    return REG_PSEUDO_HALF_VOICING.sub(lambda m: fix(m.group(), 2), s)


def execute() -> None:
    pane = cpane.CPane()
    items = pane.selectedItems
    for item in items:
        if not renamer.is_renamable(item):
            continue
        name = item.getName()
        new_name = fix_half_voicing(fix_voicing(name))
        org_path = Path(item.getFullpath())
        renamer.execute(pane, org_path, new_name)
