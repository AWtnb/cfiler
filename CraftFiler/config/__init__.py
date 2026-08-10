from . import bind_bookmark, bind_cursor_mover, command_list, main, style  # noqa: N999


def configure(window) -> None:
    main.setup(window)
    style.setup(window)
    command_list.setup(window)

    bind_bookmark.setup(window)
    bind_cursor_mover.setup(window)
