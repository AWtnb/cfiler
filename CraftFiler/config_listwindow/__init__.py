import ckit  # type:ignore  # noqa: N999

from . import main


def configure(window: ckit.TextWindow) -> None:
    main.setup(window)
