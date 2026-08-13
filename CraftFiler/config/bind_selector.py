from __future__ import annotations

from .tools import keybinder, selector


def setup(window) -> None:

    keybinder.setup(window)
    selector.setup(window)

    keybinder.bind(selector.select_byext, "S-X")
    keybinder.bind(selector.select_empty_dir, "A-E")
    keybinder.bind(selector.select_stem_contains, "Colon")
    keybinder.bind(selector.select_stem_endswith, "S-4")
    keybinder.bind(selector.select_stem_startswith, "Caret")
    keybinder.bind(selector.unselect_panes, "C-U", "S-Esc")
    keybinder.bind(lambda: selector.select_regexp(True), "S-Colon")

    for k, v in {
        "C-A": selector.all_items,
        "U": selector.clear_all,
        "Esc": selector.clear_all,
        "A-F": selector.files,
        "A-D": selector.dirs,
        "S-Home": selector.to_top,
        "S-A": selector.to_top,
        "S-End": selector.to_bottom,
        "S-E": selector.to_bottom,
    }.items():
        keybinder.bind(v, k)
