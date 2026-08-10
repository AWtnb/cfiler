from . import (  # noqa: N999
    bind_bookmark,
    bind_cursor_jumper,
    bind_cursor_mover,
    command_list,
    main,
    style,
)


def configure(window) -> None:
    main.setup(window)
    style.setup(window)
    command_list.setup(window)

    bind_bookmark.setup(window)
    bind_cursor_mover.setup(window)
    bind_cursor_jumper.setup(window)
