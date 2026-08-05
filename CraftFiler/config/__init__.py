from cfiler_mainwindow import MainWindow  # noqa: N999  # type: ignore

from . import main


def configure(window: MainWindow) -> None:
    main.setup(window)
