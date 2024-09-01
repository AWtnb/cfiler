import importlib
from setting import setup


def configure(window) -> None:
    importlib.reload(setup)
    setup.configure(window)


def configure_ListWindow(window) -> None:
    importlib.reload(setup)
    setup.configure_ListWindow(window)


def configure_TextViewer(window) -> None:
    importlib.reload(setup)
    setup.configure_TextViewer(window)


def configure_ImageViewer(window) -> None:
    importlib.reload(setup)
    setup.configure_ImageViewer(window)
