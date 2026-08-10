from cfiler_mainwindow import MainWindow  # noqa: N999  # type: ignore

from . import command_list, main, style


def configure(window: MainWindow) -> None:
    main.setup(window)
    style.setup(window)
    command_list.setup(window)
