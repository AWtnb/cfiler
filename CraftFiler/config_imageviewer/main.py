import os
import subprocess

import cfiler_resource  # ty: ignore[unresolved-import]
import ckit  # ty: ignore[unresolved-import]
import pyauto  # ty: ignore[unresolved-import]


def setup(window) -> None:
    window.keymap["F11"] = window.command_ToggleMaximize
    window.keymap["H"] = window.command_CursorUp
    window.keymap["J"] = window.command_CursorDown
    window.keymap["K"] = window.command_CursorUp
    window.keymap["L"] = window.command_CursorDown
    window.keymap["S-Semicolon"] = window.command_ZoomIn
    window.keymap["Z"] = window.command_ZoomIn
    window.keymap["Minus"] = window.command_ZoomOut
    window.keymap["S-Z"] = window.command_ZoomOut
    window.keymap["S-Minus"] = window.command_ZoomPolicyOriginal
    window.keymap["Left"] = window.command_CursorUp
    window.keymap["Right"] = window.command_CursorDown
    window.keymap["Down"] = window.command_CursorDown
    window.keymap["Up"] = window.command_CursorUp
    window.keymap["S-Left"] = window.command_ScrollLeft
    window.keymap["S-Right"] = window.command_ScrollRight
    window.keymap["S-Down"] = window.command_ScrollDown
    window.keymap["S-Up"] = window.command_ScrollUp
    window.keymap["S-H"] = window.command_ScrollLeft
    window.keymap["S-L"] = window.command_ScrollRight
    window.keymap["S-J"] = window.command_ScrollDown
    window.keymap["S-K"] = window.command_ScrollUp
    window.keymap["Q"] = window.command_Close

    def to_top(_) -> None:
        if 0 < window.job_queue.numItems():
            return
        if window.cursor == 0:
            return
        window.cursor = 0
        if window.cursor_handler:
            window.cursor_handler(window.items[window.cursor])
        window.decode()

    window.keymap["A"] = to_top
    window.keymap["Home"] = to_top

    def to_last(_) -> None:
        if 0 < window.job_queue.numItems():
            return
        last = len(window.items) - 1
        if window.cursor == last:
            return
        window.cursor = last
        if window.cursor_handler:
            window.cursor_handler(window.items[window.cursor])
        window.decode()

    window.keymap["E"] = to_last
    window.keymap["End"] = to_last

    def toggle_zoom(_) -> None:
        if window.zoom_policy == "original":
            window.command_ZoomPolicyFit(None)
        else:
            window.command_ZoomPolicyOriginal(None)

    window.keymap["O"] = toggle_zoom
    window.keymap["F"] = toggle_zoom

    def open_original(_) -> None:
        item = window.items[window.cursor]
        path = item.getFullpath()
        window.command_Close(None)
        pyauto.shellExecute(None, path, "", "")

    window.keymap["C-Enter"] = open_original
    window.keymap["C-L"] = open_original

    def copy_path_to_clioboard(_) -> None:
        item = window.items[window.cursor]
        path = item.getFullpath()
        ckit.setClipboardText(path)
        window.setTitle(
            f"{cfiler_resource.cfiler_appname} - [ {window.items[window.cursor].name} ] path copied!"
        )

    window.keymap["C-S-C"] = copy_path_to_clioboard

    def copy_image_to_clioboard(_) -> None:
        ps1_path = os.path.join(ckit.dataPath(), "powershell", "clipimg.ps1")

        def _copy(_) -> None:
            item = window.items[window.cursor]
            cmd = f'PowerShell -NoProfile -ExecutionPolicy Bypass -File "{ps1_path}" {item.getFullpath()}'
            subprocess.run(
                cmd, creationflags=subprocess.CREATE_NO_WINDOW, shell=True, check=False
            )

        def _finished(_) -> None:
            window.setTitle(
                f"{cfiler_resource.cfiler_appname} - [ {window.items[window.cursor].name} ] copied!"
            )

        job = ckit.JobItem(_copy, _finished)
        window.job_queue.enqueue(job)

    window.keymap["C-C"] = copy_image_to_clioboard
