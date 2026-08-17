from __future__ import annotations

from . import cpane


def setup(window) -> None:
    cpane.setup(window)


def get_block_edges(idxs: list[int]) -> list[int]:
    if len(idxs) < 1:
        return []

    edges = []
    start = idxs[0]
    end = start

    for idx in idxs[1:]:
        if idx == end + 1:
            end = idx
        else:
            edges.append(start)
            edges.append(end)
            start = idx
            end = idx

    edges.append(start)
    if 0 < len(edges) and edges[-1] != end:
        edges.append(end)
    return edges


def get_base_edges(pane: cpane.CPane) -> list[int]:
    edges = [0]
    edges.append(pane.count - 1)
    if 0 < (nd := len(pane.dirs)):
        edges.append(nd - 1)
        if 0 < len(pane.files):
            edges.append(nd)
    return edges


def get_item_edges(pane: cpane.CPane) -> list[int]:
    if pane.isBlank:
        return []
    stack = get_base_edges(pane)
    for i in range(pane.count):
        item = pane.byIndex(i)
        if item.bookmark() or item.selected():
            stack.append(i)
    stack = get_block_edges(stack)
    return sorted(set(stack))


def get_prefix_edges(pane: cpane.CPane) -> list[int]:
    if pane.isBlank:
        return []
    names = pane.names
    if len(names) < 2:
        return []
    prefs = [name.split("_", 1)[0] for name in names]
    edges = get_base_edges(pane)
    start = 0
    for i in range(1, len(prefs) + 1):
        if i == len(prefs) or prefs[i] != prefs[start]:
            if 1 < i - start:
                edges += [start, i - 1]
            start = i
    return sorted(set(edges))


def jump_down(by_prefix: bool, selecting: bool) -> None:
    pane = cpane.CPane()
    dests = get_prefix_edges(pane) if by_prefix else get_item_edges(pane)
    if len(dests) < 1:
        return
    cur = pane.cursor
    idx = -1
    for t in dests:
        if cur < t:
            idx = t
            break
    if idx < 0:
        return
    if selecting:
        for i in range(pane.count):
            if cur <= i <= idx:
                pane.select(i)
    pane.focus(idx)


def jump_up(by_prefix: bool, selecting: bool) -> None:
    pane = cpane.CPane()
    dests = get_prefix_edges(pane) if by_prefix else get_item_edges(pane)
    if len(dests) < 1:
        return
    cur = pane.cursor
    idx = -1
    for t in dests:
        if t < cur:
            idx = t
    if idx < 0:
        return
    if selecting:
        for i in range(pane.count):
            if idx <= i <= cur:
                pane.select(i)
    pane.focus(idx)
