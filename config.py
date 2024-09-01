import sys
sys.dont_write_bytecode = True

import importlib
from setting import setup


def configure(window) -> None:
    importlib.reload(setup)
    setup.configure(window)


def configure_ListWindow(window) -> None:
    setup.configure_ListWindow(window)


def configure_TextViewer(window) -> None:
    setup.configure_TextViewer(window)


def configure_ImageViewer(window) -> None:
    setup.configure_ImageViewer(window)
