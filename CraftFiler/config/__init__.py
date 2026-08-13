import ckit  # type: ignore  # noqa: N999

from . import (
    bind_bookmark,
    bind_change_dir,
    bind_clipboard,
    bind_cursor_jumper,
    bind_cursor_mover,
    bind_filter,
    bind_item_handler,
    bind_main,
    bind_misc,
    bind_renamer,
    bind_selector,
    bind_snapper,
    command_list,
    style,
)
from .tools import clon, enter


def configure(window) -> None:

    style.setup(window)

    clon.setup(window)
    ckit.CronTable.defaultCronTable().add(clon.invoke_tempfile_cleaner())

    enter.setup(window)
    window.enter_hook = enter.hook_enter

    bind_bookmark.setup(window)
    bind_change_dir.setup(window)
    bind_clipboard.setup(window)
    bind_cursor_jumper.setup(window)
    bind_cursor_mover.setup(window)
    bind_filter.setup(window)
    bind_item_handler.setup(window)
    bind_main.setup(window)
    bind_misc.setup(window)
    bind_renamer.setup(window)
    bind_selector.setup(window)
    bind_snapper.setup(window)

    command_list.setup(window)
