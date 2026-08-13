from __future__ import annotations

from .tools import change_dir, keybinder


def setup(window) -> None:
    change_dir.setup(window)

    keybinder.bind(change_dir.change_drive, "D")
    keybinder.bind(change_dir.go_to, "C-G")
    keybinder.bind(change_dir.open_latest_under_tree, "S-A-N")
    keybinder.bind(change_dir.to_ghq_repo, "G")
    keybinder.bind(change_dir.zyw.invoke(skip_file=False), "S-Z")
    keybinder.bind(change_dir.zyw.invoke(skip_file=True), "Z")
