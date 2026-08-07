from __future__ import annotations

from typing import NamedTuple

import pyauto  # type: ignore


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window


class Rect(NamedTuple):
    left: int
    top: int
    right: int
    bottom: int

    def get_half(self) -> tuple:
        width = self.right - self.left
        height = self.bottom - self.top
        if height < width:
            return (self.left + self.right) // 2, self.top, self.right, self.bottom
        return self.left, (self.top + self.bottom) // 2, self.right, self.bottom


def to_home_position() -> None:
    hwnd = window.getHWND()
    wnd = pyauto.Window.fromHWND(hwnd)

    if wnd.isMaximized():
        wnd.restore()

    monitor_infos = pyauto.Window.getMonitorInfo()
    monitor_infos.sort(key=lambda info: info[2] != 1)

    monitor_rects = [Rect(*mi[1]) for mi in monitor_infos]
    half_rects = [r.get_half() for r in monitor_rects]
    current = wnd.getRect()

    idx = half_rects.index(current) if current in half_rects else -1
    dest = half_rects[(idx + 1) % len(half_rects)]

    counter = 0
    while wnd.getRect() != dest:
        if 10 < counter:
            return
        wnd.setRect(dest)
        counter += 1

    window.command_MoveSeparatorCenter(None)
