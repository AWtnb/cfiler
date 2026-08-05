import subprocess

import ckit  # type: ignore

from . import kiritori
from .cpane import CPane
from .protocols import ItemDefaultProtocol


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    kiritori.setup(window)


def smart_cursorUp() -> None:
    pane = CPane()
    if pane.isBlank or pane.count == 1:
        return
    if pane.cursor == 0:
        pane.entity.cursor = pane.count - 1
    else:
        pane.entity.cursor -= 1
    pane.scrollToCursor()


def smart_cursorDown() -> None:
    pane = CPane()
    if pane.isBlank or pane.count == 1:
        return
    if pane.cursor == pane.count - 1:
        pane.entity.cursor = 0
    else:
        pane.entity.cursor += 1
    pane.scrollToCursor()


def focus_latest_item() -> None:
    pane = CPane()
    if pane.isBlank:
        return

    candidates: list[ItemDefaultProtocol] = []
    for item in pane.selectedOrAllItems:
        if len(candidates) == 0:
            candidates.append(item)
            continue
        latest = candidates[-1]
        if latest.time() <= item.time():
            if latest.time() == item.time():
                candidates.append(item)
            else:
                candidates = [item]

    if len(candidates) < 1:
        return

    candidate_names = [c.getName() for c in candidates]
    current_focused = pane.focusedItem.getName()
    try:
        idx = candidate_names.index(current_focused)
        pane.focusByName(candidate_names[(idx + 1) % len(candidate_names)])
    except ValueError:
        pane.focusByName(candidate_names[0])


def focus_by_timestamp() -> None:
    pane = CPane()
    if pane.isBlank:
        return

    focused = pane.focusedItem
    base = focused.time()

    older: list[ItemDefaultProtocol] = []
    sametime: list[ItemDefaultProtocol] = []
    for item in pane.selectedOrAllItems:
        ts = item.time()
        if ts == base:
            sametime.append(item)
        else:
            if ts < base:
                older.append(item)

    if 0 < len(sametime):
        idx = [item.getName() for item in sametime].index(focused.getName())
        if 0 < idx:
            pane.focusByName(sametime[idx - 1].getName())
            return

    if 0 < len(older):
        last = max(older, key=lambda x: x.time())
        pane.focusByName(last.getName())


def fuzzy_focus() -> None:
    pane = CPane()
    names = pane.names
    if len(names) < 1:
        return

    def _select(job_item: ckit.JobItem) -> None:
        job_item.selected = None
        proc = subprocess.run(
            [
                "fzf.exe",
                "--margin=1",
                "--no-color",
                "--input-border=sharp",
                "--layout=reverse",
            ],
            input="\n".join(names),
            capture_output=True,
            encoding="utf-8",
            check=False,
        )

        if proc.returncode != 0 and (e := proc.stderr):
            kiritori.log(e)
            return
        job_item.selected = proc.stdout.strip()

    def _focus(job_item: ckit.JobItem) -> None:
        name = job_item.selected
        if name is not None:
            pane.focusByName(name)

    job = ckit.JobItem(_select, _focus)
    window.taskEnqueue(job, create_new_queue=False)
