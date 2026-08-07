from __future__ import annotations

from enum import Enum
from typing import Literal

from cfiler_listwindow import ListWindow  # type: ignore


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window


def invoke(
    prompt: str,
    items: list,
    cursor_pos: int = 0,
    onkeypress: Literal["navigate", "search", "search_and_decide"] = "navigate",
) -> tuple[int, int]:
    pos = window.centerOfFocusedPaneInPixel()
    list_window = ListWindow(
        x=pos[0],
        y=pos[1],
        min_width=40,
        min_height=1,
        max_width=window.width() - 5,
        max_height=window.height() - 3,
        parent_window=window,
        ini=window.ini,
        title=prompt,
        items=items,
        initial_select=cursor_pos,
        onekey_search=onkeypress.startswith("search"),
        onekey_decide=onkeypress.endswith("decide"),
        return_modkey=True,
        keydown_hook=None,
        statusbar_handler=None,
    )
    window.enable(False)
    list_window.messageLoop()
    result, mod = list_window.getResult()
    window.enable(True)
    window.activate()
    list_window.destroy()
    return result, mod


def ask_open_by_vscode() -> bool | None:
    class App(Enum):
        CFILER = "CFiler"
        VSCODE = "VSCode"

    apps = [App.CFILER, App.VSCODE]

    result, _ = invoke("Open with:", [app.value for app in apps])
    if result < 0:
        return None

    selected = apps[result]

    return selected == App.VSCODE
