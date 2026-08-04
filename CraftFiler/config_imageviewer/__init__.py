from cfiler_mainwindow import MainWindow  # noqa: N999  # ty: ignore[unresolved-import]

from . import main


def configure(window: MainWindow) -> None:
    main.setup(window)
