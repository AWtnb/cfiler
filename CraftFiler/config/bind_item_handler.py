from __future__ import annotations

from .tools import item_handler, keybinder


def setup(window) -> None:

    item_handler.setup(window)

    keybinder.bind(item_handler.duplicate_with_new_extension, "A-S-D")
    keybinder.bind(item_handler.duplicate_with_new_stem, "S-D")
    keybinder.bind(item_handler.open_on_explorer, "C-S-E")
    keybinder.bind(item_handler.open_parent_to_other, "S-U")
    keybinder.bind(item_handler.open_to_other, "S-L")
    keybinder.bind(item_handler.quick_copy, "C")
    keybinder.bind(item_handler.quick_move, "M")
    keybinder.bind(item_handler.recylcebin, "Delete")
    keybinder.bind(item_handler.smart_mkdir, "C-S-N")
    keybinder.bind(item_handler.touch_new_file, "T")
    keybinder.bind(lambda: item_handler.smart_copy_to_dir(False), "S-C")
    keybinder.bind(lambda: item_handler.smart_copy_to_dir(True), "S-M")
