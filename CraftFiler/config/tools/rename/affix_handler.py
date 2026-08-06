from __future__ import annotations

import os
from typing import Callable

import ckit  # type: ignore

from .. import cpane
from ..common import get_now


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    cpane.setup(window)


def to_stem(path: str) -> str:
    _, name = os.path.split(path)
    stem, _ = os.path.splitext(name)
    return stem


def len_ordered(lines: set[str]) -> list[str]:
    return sorted(set(lines), key=len)


SEP = "_"


def get_selected_stems() -> list[str]:
    sels = cpane.CPane().selectedItemPaths + cpane.CPane(False).selectedItemPaths
    return sorted([to_stem(sel) for sel in sels])


def get_prefix_candidates(pane: cpane.CPane) -> set[str]:
    candidates = set()
    for path in pane.paths:
        stem = to_stem(path)
        for i, c in enumerate(stem):
            if 0 < i and c == SEP:
                candidates.add(stem[: i + 1])
    return candidates


def filter_prefixes(candidates: set[str], user_input: str) -> list[str]:
    return len_ordered({c for c in candidates if c.startswith(user_input)})


def invoke_prefix_handler() -> Callable[
    [ckit.ckit_widget.EditWidget.UpdateInfo], tuple[list[str], int]
]:
    selected = get_selected_stems()
    candidates = get_prefix_candidates(cpane.CPane())

    def _handler(
        update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
    ) -> tuple[list[str], int]:
        matched = filter_prefixes(candidates, update_info.text)
        return selected + matched, 0

    return _handler


def get_suffix_candidates(pane: cpane.CPane) -> set[str]:
    candidates = set()
    candidates.add(f"_{get_now().strftime('%Y%m%d')}")
    for path in pane.paths:
        stem = to_stem(path)
        for i, c in enumerate(stem):
            if 0 < i and c == SEP:
                candidates.add(stem[i:])
    return candidates


def filter_suffixes(candidates: set[str], user_input: str) -> list[str]:
    if SEP not in user_input:
        return len_ordered({user_input + c for c in candidates})

    if user_input.endswith(SEP):
        return len_ordered({user_input + c[1:] for c in candidates})

    found = set()
    sep_pos = user_input.find(SEP)
    after_first_sep = user_input[sep_pos:]
    for c in candidates:
        if c.startswith(after_first_sep):
            found.add(user_input + c[len(after_first_sep) :])
    return len_ordered(found)


def invoke_suffix_handler() -> Callable[
    [ckit.ckit_widget.EditWidget.UpdateInfo], tuple[list[str], int]
]:
    selected = get_selected_stems()
    candidates = get_suffix_candidates(cpane.CPane())

    def _handler(
        update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
    ) -> tuple[list[str], int]:
        matched = filter_suffixes(candidates, update_info.text)
        return selected + matched, 0

    return _handler
