import ckit  # ty: ignore[unresolved-import]


def setup(window: ckit.TextWindow) -> None:

    def refresh() -> None:
        window.scroll_info.makeVisible(
            window.select, window.itemsHeight(), window.scroll_margin
        )
        window.paint()

    def to_top(_) -> None:
        window.select = 0
        refresh()

    def to_bottom(_) -> None:
        window.select = len(window.items) - 1
        refresh()

    def smart_cursorUp(_) -> None:
        if window.select == 0:
            window.select = len(window.items) - 1
        else:
            window.select -= 1
        refresh()

    def smart_cursorDown(_) -> None:
        if window.select == len(window.items) - 1:
            window.select = 0
        else:
            window.select += 1
        refresh()

    window.keymap["Home"] = to_top
    window.keymap["End"] = to_bottom
    window.keymap["Down"] = smart_cursorDown
    window.keymap["Up"] = smart_cursorUp
    window.keymap["C-J"] = window.command_CursorDownMark
    window.keymap["C-K"] = window.command_CursorUpMark
    window.keymap["C-Enter"] = window.command_Enter
    for mod in ["", "S-"]:
        for key in ["Space", "Right", "C-L"]:
            window.keymap[mod + key] = window.command_Enter

    if not window.onekey_search:
        window.keymap["A"] = to_top
        window.keymap["E"] = to_bottom
        window.keymap["J"] = smart_cursorDown
        window.keymap["K"] = smart_cursorUp
        window.keymap["L"] = window.command_Enter
