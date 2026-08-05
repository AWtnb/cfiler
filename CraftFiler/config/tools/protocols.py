from __future__ import annotations

from typing import Protocol

import ckit  # type: ignore
from cfiler import *  # type: ignore
from cfiler_filelist import FileList  # type: ignore


class PaneHistoryProtocol(Protocol):
    def append(self, parent: str, name: str, visible: bool, mark: bool) -> None: ...

    items: list


class PaneEntityProtocol(Protocol):
    cursor: int
    history: PaneHistoryProtocol
    file_list: FileList
    scroll_info: ckit.ScrollInfo


class ItemDefaultProtocol(Protocol):
    def isdir(self) -> bool: ...
    def getName(self) -> str: ...
    def getFullpath(self) -> str: ...
    def bookmark(self) -> list: ...
    def time(self) -> tuple: ...
    def selected(self) -> bool: ...
    def size(self) -> int: ...
