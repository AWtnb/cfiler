import importlib
import sys
from types import ModuleType

import ckit  # ty: ignore[unresolved-import]
from cfiler_mainwindow import MainWindow  # ty: ignore[unresolved-import]


def setup_config(config_module_name: str) -> ModuleType:
    config_dir = ckit.dataPath()
    if config_dir not in sys.path:
        sys.path.insert(0, config_dir)

    for name in list(sys.modules):
        if name == config_module_name or name.startswith(config_module_name + "."):
            del sys.modules[name]
    return importlib.import_module(config_module_name)


def configure(window: MainWindow) -> None:
    config = setup_config("config")
    config.configure(window)


def configure_ListWindow(window: ckit.TextWindow) -> None:
    config = setup_config("config_listwindow")
    config.configure(window)


def configure_TextViewer(window: ckit.TextWindow) -> None:
    config = setup_config("config_textviewer")
    config.configure(window)


def configure_ImageViewer(window: ckit.TextWindow) -> None:
    config = setup_config("config_imageviewer")
    config.configure(window)
