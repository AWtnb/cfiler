from __future__ import annotations

import configparser
import datetime
import hashlib
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Iterator, NamedTuple

import cfiler_msgbox  # type: ignore
import ckit  # type: ignore
import pyauto  # type: ignore
from cfiler import *  # type: ignore
from cfiler_filelist import filter_Default  # type: ignore
from cfiler_resultwindow import popResultWindow  # type: ignore
from PIL import Image as PILImage  # type: ignore
from PIL import ImageGrab  # type: ignore
from PIL.ExifTags import TAGS  # type: ignore

from . import style
from .tools import (
    archiver,
    bookmark,
    change_dir,
    clon,
    cpane,
    cursor_jumper,
    cursor_mover,
    enter,
    keybinder,
    kiritori,
    listwindow,
    office,
    selector,
)
from .tools.archiver import compress_files, extract_archives
from .tools.bookmark import (
    bookmark_here,
    fuzzy_bookmark,
    set_bookmark_alias,
    toggle_bookmark,
)
from .tools.change_dir import (
    change_drive,
    go_to,
    open_latest_under_tree,
    to_ghq_repo,
    zyw,
)
from .tools.clon import invoke_tempfile_cleaner, remove_tempfiles
from .tools.common import (
    DESKTOP_PATH,
    CallbackFunc,
    PaintOption,
    open_vscode,
    resolve_scoop_shim,
    run_ps1,
    shell_exec,
    smart_check_path,
    stringify,
)
from .tools.cpane import CPane, LeftPane, RightPane, adjust_pane_width, swap_pane
from .tools.cursor_jumper import CursorJumper
from .tools.cursor_mover import (
    focus_by_timestamp,
    focus_latest_item,
    fuzzy_focus,
    smart_cursorDown,
    smart_cursorUp,
)
from .tools.enter import hook_enter, open_with
from .tools.listwindow import invoke_listwindow
from .tools.office import docx_to_txt, read_openxml
from .tools.protocols import ItemDefaultProtocol


def setup(window) -> None:

    archiver.setup(window)
    bookmark.setup(window)
    change_dir.setup(window)
    clon.setup(window)
    cpane.setup(window)
    cursor_jumper.setup(window)
    cursor_mover.setup(window)
    enter.setup(window)
    keybinder.setup(window)
    kiritori.setup(window)
    listwindow.setup(window)
    office.setup(window)
    selector.setup(window)
    style.setup(window)

    window.enter_hook = hook_enter

    def reset_default_keys(keys: list) -> None:
        for key in keys:
            window.keymap[key] = lambda _: None

    reset_default_keys(
        [
            "Q",
            "Colon",
            "S-Colon",
            "Period",
            "S-Period",
            "BackSlash",
        ]
    )

    def apply_cfiler_command(mapping: dict) -> None:
        for key, func in mapping.items():
            window.keymap[key] = func

    apply_cfiler_command(
        {
            "S-Enter": window.command_View,
            "C-S-Q": window.command_CancelTask,
            "C-Comma": window.command_ConfigMenu,
            "C-S-Comma": window.command_ConfigMenu2,
            "C-H": window.command_JumpHistory,
            "C-Z": window.command_JumpHistory,
            "Back": window.command_JumpHistory,
            "C-D": window.command_Delete,
            "P": window.command_FocusOther,
            "C-Right": window.command_FocusOther,
            "O": window.command_ChdirActivePaneToOther,
            "S-O": window.command_ChdirInactivePaneToOther,
            "A": window.command_CursorTop,
            "E": window.command_CursorBottom,
            "Home": window.command_CursorTop,
            "End": window.command_CursorBottom,
            "C-S-P": window.command_CommandLine,
            "H": window.command_GotoParentDir,
            "Left": window.command_GotoParentDir,
            "S-F10": window.command_ContextMenu,
            "A-S-F10": window.command_ContextMenuDir,
            "Apps": window.command_ContextMenu,
            "S-Apps": window.command_ContextMenuDir,
            "OpenBracket": window.command_MoveSeparatorLeft,
            "CloseBracket": window.command_MoveSeparatorRight,
            "Yen": window.command_MoveSeparatorCenter,
            "A-S": window.command_SetSorter,
            "S-J": window.command_LogDown,
            "S-K": window.command_LogUp,
            "S-OpenBracket": window.command_MoveSeparatorUp,
            "S-CloseBracket": window.command_MoveSeparatorDown,
            "C-S-R": window.command_BatchRename,
        }
    )

    keybinder.bind(toggle_bookmark, "C-B")
    keybinder.bind(lambda: fuzzy_bookmark(False), "B")
    keybinder.bind(lambda: fuzzy_bookmark(True), "A-S-B")

    def new_cfiler_window() -> None:
        exe_path = sys.executable
        if smart_check_path(exe_path):
            slashed = DESKTOP_PATH.replace("\\", "/")
            pyauto.shellExecute(
                None,
                exe_path,
                f' -L"{slashed}" -R"{slashed}"',
            )
        else:
            kiritori.log(f"{exe_path} not found.")

    keybinder.bind(new_cfiler_window, "C-N")

    keybinder.bind(smart_cursorUp, "K", "Up")
    keybinder.bind(smart_cursorDown, "J", "Down")
    keybinder.bind(focus_latest_item, "A-N")

    def select_empty_dir() -> None:
        pane = CPane()
        for d in pane.dirs:
            path = Path(d.getFullpath())
            if not any(path.iterdir()):
                pane.selectByName(path.name)

    keybinder.bind(select_empty_dir, "A-E")

    def copy_dir_tree() -> None:
        pane = CPane()
        selected_names = pane.selectedItemNames
        root = pane.currentPath
        window.setProgressValue(None)

        def _traverse(job_item: ckit.JobItem) -> None:
            job_item.paths = []
            for item in pane.traverse(False):
                if job_item.isCanceled():
                    return
                rel = item.getFullpath()[len(root) :].lstrip(os.sep)
                if len(selected_names) < 1 or any(
                    (rel == name or rel.startswith(name + os.sep))
                    for name in selected_names
                ):
                    job_item.paths.append(rel)

        def _finished(job_item: ckit.JobItem) -> None:
            window.clearProgress()
            if job_item.isCanceled():
                kiritori.log("Canceled.")
            else:
                lines = "\n".join(sorted(job_item.paths))
                ckit.setClipboardText(lines)
                kiritori.log(f"Copied tree: {root}")

        job = ckit.JobItem(_traverse, _finished)
        window.taskEnqueue(job, create_new_queue=False)

    keybinder.bind(open_latest_under_tree, "S-A-N")
    keybinder.bind(focus_by_timestamp, "A-Back", "A-B")

    def git_init() -> None:
        pane = CPane()
        path = pane.currentPath
        git_path = os.path.join(path, ".git")
        if smart_check_path(git_path):
            kiritori.log(f"'{git_path}' already exists.")
            return
        shell_exec("git", "init", str(path))

    def open_lazygit() -> None:
        pane = CPane()
        path = pane.currentPath

        lazygit = "lazygit"
        if shutil.which(lazygit) is None:
            kiritori.log(f"'{lazygit}' not found...")
            return

        git_path = os.path.join(path, ".git")
        if not smart_check_path(git_path):
            kiritori.log(f"'{git_path}' not found.")
            return

        shell_exec("wt.exe", "lazygit", "-p", path)

    keybinder.bind(open_lazygit, "A-L")

    keybinder.bind(adjust_pane_width, "C-S")

    keybinder.bind(lambda: CPane().focusOther(), "C-L")

    keybinder.bind(window.command_Enter, "L", "Right")

    def toggle_hidden() -> None:
        window.showHiddenFile(not window.isHiddenFileVisible())

    keybinder.bind(toggle_hidden, "C-S-H")

    keybinder.bind(open_with, "C-O")

    def open_with_smooth_csv(_) -> None:
        smooth_csv_path = r"C:\Program Files\SmoothCSV\smoothcsv-app.exe"
        if not smart_check_path(smooth_csv_path):
            return

        pane = CPane()
        target = pane.selectedItemPaths
        if len(target) < 1:
            target = [pane.focusedItemPath]

        for p in target:
            if Path(p).suffix in [".csv", ".txt"]:
                shell_exec(smooth_csv_path, p)

    keybinder.bind(open_with_smooth_csv, "Comma")

    def quick_move() -> None:
        pane = CPane()
        if not pane.hasSelection:
            window.command_Select(None)
        pane.adjustWidth()
        window.command_Move(None)

    keybinder.bind(quick_move, "M")

    def quick_copy() -> None:
        pane = CPane()
        if not pane.hasSelection:
            window.command_Select(None)
        pane.adjustWidth()
        window.command_Copy(None)

    keybinder.bind(quick_copy, "C")

    keybinder.bind(swap_pane, "S")

    ckit.CronTable.defaultCronTable().add(invoke_tempfile_cleaner())

    keybinder.bind(zyw.invoke(skip_file=True), "Z")
    keybinder.bind(zyw.invoke(skip_file=False), "S-Z")
    keybinder.bind(fuzzy_focus, "S-F")

    class ImageMagickConfig:
        ini_section = "IMAGE_MAGICK_CONFIG"

        def __init__(self, option_name: str) -> None:
            try:
                window.ini.add_section(self.ini_section)
            except configparser.DuplicateSectionError:
                pass
            self._option_name = option_name

        def register(self, value: str) -> None:
            window.ini.set(self.ini_section, self._option_name, value)

        @property
        def value(self) -> str:
            try:
                return window.ini.get(self.ini_section, self._option_name)
            except Exception:
                return ""

    def change_image_type() -> None:
        exe_name = "magick.exe"
        imagemagick = shutil.which(exe_name)

        krtr = kiritori
        if imagemagick is None:
            krtr.log(f"{exe_name} not found!")
            return

        pane = CPane()
        targets = pane.selectedItemPaths
        if len(targets) < 1:
            return

        image_magick_config_ext = ImageMagickConfig("ext")
        placeholder = ""
        if 0 < len(last := image_magick_config_ext.value):
            placeholder = last

        ext = stringify(window.commandLine("NewExtension", text=placeholder))
        if ext == "":
            return

        if not ext.startswith("."):
            ext = "." + ext

        image_magick_config_ext.register(ext)

        num = len(targets)
        msg = f"Converting {num} item"
        if 1 < num:
            msg += "s"
        msg += f" to {ext}:\n"

        def _convert(job_item: ckit.JobItem) -> None:
            job_item.converted_names = []

            krtr.draw_header(msg)

            for i, path in enumerate(targets, start=1):
                p = Path(path)
                new_path = p.with_name(p.stem + ext)
                cmd = [imagemagick, path, str(new_path)]
                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    encoding="utf-8",
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False,
                )
                if proc.returncode != 0:
                    print(proc.stderr)
                else:
                    print(f"[{i:02}/{num:02}]{new_path.name}")
                    job_item.converted_names.append(p.name)

        def _finish(job_item: ckit.JobItem) -> None:
            names = job_item.converted_names
            for name in names:
                pane.unSelectByName(name)
            if 0 < len(names):
                krtr.draw_footer()

        job = ckit.JobItem(_convert, _finish)
        window.taskEnqueue(job, create_new_queue=False)

    def concatenate_pdf() -> None:
        exe_name = "go-pdfconc.exe"
        exe_path = shutil.which(exe_name)
        if not exe_path:
            kiritori.log(f"'{exe_name}' not found!")
            return

        pane = CPane()
        if not pane.hasSelection:
            return
        for path in pane.selectedItemPaths:
            p = Path(path)
            if p.is_dir():
                kiritori.log("dir item is selected!")
                return
            if p.suffix != ".pdf":
                kiritori.log("non-pdf file found!")
                return

        basename = stringify(window.commandLine(title="Outname", text="conc"))
        if len(basename) < 1:
            return

        src = "\n".join(pane.selectedItemPaths)

        def _conc(_) -> None:
            window.setProgressValue(None)
            try:
                cmd = [exe_path, "--outname", basename]
                proc = subprocess.run(
                    cmd,
                    input=src,
                    capture_output=True,
                    encoding="utf-8",
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    check=False,
                )
                if proc.returncode != 0:
                    kiritori.log(f"ERROR: {proc.stdout}")
            except Exception as e:
                kiritori.log(e)

        def _finish(job_item: ckit.JobItem) -> None:
            window.clearProgress()
            if job_item.isCanceled():
                kiritori.log("Canceled.")
            else:
                pane.refresh()
                name = basename + ".pdf"
                pane.focusByName(name)
                kiritori.log(f"Concatenated as '{name}':\n\n{src}")

        job = ckit.JobItem(_conc, _finish)
        window.taskEnqueue(job, create_new_queue=False)

    def make_internet_shortcut(url: str = "") -> None:
        if not url.startswith("http"):
            kiritori.log(f"invalid url: '{url}'")
            return

        def _access(job_item: ckit.JobItem) -> None:
            job_item.body = None
            try:
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req) as res:
                    body = res.read()
                    try:
                        text = body.decode("utf-8", errors="ignore")
                    except Exception:
                        text = body.decode("cp932", errors="ignore")
                    job_item.body = text
            except Exception as e:
                kiritori.log(e)

        def _make_shortcut(job_item: ckit.JobItem) -> None:
            title = ""
            if job_item.body is not None:
                m = re.search(
                    r"<title.*?>(.*?)</title>", job_item.body, re.IGNORECASE | re.DOTALL
                )
                title = m.group(1).strip() if m else ""

            lines = ["[InternetShortcut]"]
            domain = urllib.parse.urlparse(url).netloc
            name = stringify(
                window.commandLine(
                    "Shortcut title",
                    text=f"{title} - {domain}",
                    selection=[0, len(title)],
                )
            )
            if len(name) < 1:
                print("Canceled.\n")
                return
            lines.append(f"URL={url}")
            if not name.endswith(".url"):
                name = name + ".url"
            Path(CPane().currentPath, name).write_text(
                "\n".join(lines), encoding="utf-8"
            )

        job = ckit.JobItem(_access, _make_shortcut)
        window.taskEnqueue(job, create_new_queue=False)

    def on_paste() -> None:
        c = ckit.getClipboardText()
        if len(c) < 1:
            save_clipboard_image_as_file()
            return
        if c.startswith("http"):
            make_internet_shortcut(c)
            return
        CPane().openPath(c.strip().strip('"'))

    keybinder.bind(on_paste, "C-V", "S-Insert")
    keybinder.bind(change_drive, "D")
    keybinder.bind(go_to, "C-G")

    keybinder.bind(to_ghq_repo, "G")

    def eject_current_drive() -> None:
        pane = CPane()
        current = pane.currentPath
        if current.startswith("C:"):
            return

        current_drive = Path(current).drive
        other = CPane(False)
        if other.currentPath.startswith(current_drive):
            other.openPath(DESKTOP_PATH)

        pane.openPath(DESKTOP_PATH)

        def _eject(job_item: ckit.JobItem) -> None:
            job_item.result = None
            proc = run_ps1("eject", current_drive)
            if proc.returncode != 0:
                if o := proc.stdout:
                    kiritori.log(o)
                if e := proc.stderr:
                    kiritori.log(e)
                return
            job_item.result = f"Ejected drive '{current_drive}'"

        def _finished(job_item: ckit.JobItem) -> None:
            if job_item.result is None:
                pane.openPath(current)
                kiritori.log(f"Failed to eject drive '{current_drive}'")
            else:
                kiritori.log(job_item.result)

        job = ckit.JobItem(_eject, _finished)
        window.taskEnqueue(job, create_new_queue=False)

    def recylcebin() -> None:
        shell_exec("shell:RecycleBinFolder")

    keybinder.bind(recylcebin, "Delete")

    def copy_current_path() -> None:
        pane = CPane()
        p = pane.currentPath
        ckit.setClipboardText(p)
        window.setStatusMessage(f"copied current path: '{p}'", 3000)

    keybinder.bind(copy_current_path, "C-A-P")

    def on_copy() -> None:
        selection_left, selection_right = window.log_pane.selection
        if selection_left != selection_right:
            window.command_SetClipboard_LogSelected(None)
            return

        pane = CPane()

        targets = []
        if pane.isBlank:
            targets.append(pane.currentPath)
        else:
            targets = pane.selectedItemPaths
            if len(targets) < 1:
                targets.append(pane.focusedItemPath)

        menu = ["Fullpath", "Name"]
        if any([Path(t).is_file() for t in targets]):
            menu.append("Basename")

        if all([Path(path).suffix in [".docx", ".xlsx"] for path in targets]):
            menu.append("Text content")

        result, _ = invoke_listwindow("Copy", menu)
        if result < 0:
            return

        def _copy(job_item: ckit.JobItem) -> None:
            lines = []
            for target in targets:
                if result == 0:
                    lines.append(target)
                    continue
                p = Path(target)
                if result == 1:
                    lines.append(p.name)
                    continue
                if result == 3:
                    content = read_openxml(target)
                    lines.append(content)
                    continue
                lines.append(p.stem)
            ckit.setClipboardText("\n".join(lines))
            job_item.count = len(lines)

        def _finished(job_item: ckit.JobItem) -> None:
            s = f"Copied {job_item.count} {menu[result]}"
            if 1 < job_item.count:
                s += "s"
            s += "."
            window.setStatusMessage(s, 2000)

        job = ckit.JobItem(_copy, _finished)
        window.taskEnqueue(job, create_new_queue=False)

    keybinder.bind(on_copy, "C-C")

    def bind_selector() -> None:
        for k, v in {
            "C-A": selector.all_items,
            "U": selector.clear_all,
            "Esc": selector.clear_all,
            "A-F": selector.files,
            "A-D": selector.dirs,
            "S-Home": selector.to_top,
            "S-A": selector.to_top,
            "S-End": selector.to_bottom,
            "S-E": selector.to_bottom,
        }.items():
            keybinder.bind(v, k)

    bind_selector()

    def unselect_panes() -> None:
        CPane().unSelectAll()
        CPane(False).unSelectAll()

    keybinder.bind(unselect_panes, "C-U", "S-Esc")

    def smart_jumpDown(by_prefix: bool, selecting: bool) -> CallbackFunc:
        def _jumper() -> None:
            CursorJumper(by_prefix).down(selecting)

        return _jumper

    keybinder.bind(smart_jumpDown(True, False), "A-J")
    keybinder.bind(smart_jumpDown(True, True), "S-A-J")
    keybinder.bind(smart_jumpDown(False, False), "C-J")
    keybinder.bind(smart_jumpDown(False, True), "S-C-J")

    def smart_jumpUp(by_prefix: bool, selecting: bool) -> CallbackFunc:
        def _jumper() -> None:
            CursorJumper(by_prefix).up(selecting)

        return _jumper

    keybinder.bind(smart_jumpUp(True, False), "A-K")
    keybinder.bind(smart_jumpUp(True, True), "S-A-K")
    keybinder.bind(smart_jumpUp(False, False), "C-K")
    keybinder.bind(smart_jumpUp(False, True), "S-C-K")

    def duplicate_pane() -> None:
        window.command_ChdirInactivePaneToOther(None)
        pane = CPane()
        pane.focusOther()

    keybinder.bind(duplicate_pane, "W")

    def open_on_explorer() -> None:
        pane = CPane(True)
        shell_exec(pane.currentPath)

    keybinder.bind(open_on_explorer, "C-S-E")

    def open_to_other() -> None:
        pane = CPane(True)
        if not pane.isBlank:
            CPane(False).openPath(pane.focusedItemPath)
            pane.focusOther()

    keybinder.bind(open_to_other, "S-L")

    def open_parent_to_other() -> None:
        pane = CPane(True)
        parent, current_name = os.path.split(pane.currentPath)
        CPane(False).openPath(parent, current_name)
        pane.focusOther()

    keybinder.bind(open_parent_to_other, "S-U")

    def on_vscode() -> None:
        pane = CPane()
        open_vscode(pane.currentPath)

    keybinder.bind(on_vscode, "V")

    class Renamer:
        def __init__(self) -> None:
            self._pane = CPane()

        @staticmethod
        def renamable(item) -> bool:
            return (
                hasattr(item, "rename")
                and hasattr(item, "utime")
                and hasattr(item, "uattr")
            )

        @property
        def candidate(self) -> list:
            if self._pane.hasSelection:
                items = []
                for item in self._pane.selectedItems:
                    if self.renamable(item):
                        items.append(item)
                return items
            item = self._pane.focusedItem
            if self.renamable(item):
                return [item]
            return []

        def execute(self, org_path: Path, new_name: str, focus: bool = False) -> None:
            new_path = org_path.with_name(new_name)
            if smart_check_path(new_path):
                if new_path.name in [c.name for c in new_path.parent.iterdir()]:
                    print(f"'{new_name}' already exists!")
                    return
            try:
                window.subThreadCall(org_path.rename, (str(new_path),))
                print(f"Renamed: {org_path.name}\n     ==> {new_name}\n")
                self._pane.refresh()
                if focus:
                    self._pane.focusByName(new_name)
            except Exception as e:
                print(e)

    class RenameConfig:
        ini_section = "RENAME_CONFIG"

        def __init__(self, option_name: str) -> None:
            try:
                window.ini.add_section(self.ini_section)
            except configparser.DuplicateSectionError:
                pass
            self._option_name = option_name

        def register(self, value: str) -> None:
            window.ini.set(self.ini_section, self._option_name, value)

        @property
        def value(self) -> str:
            try:
                return window.ini.get(self.ini_section, self._option_name)
            except Exception:
                return ""

    class RenameInfo(NamedTuple):
        orgPath: Path
        newName: str

    def rename_substr() -> None:
        renamer = Renamer()

        targets = renamer.candidate
        if len(targets) < 1:
            return

        placeholder = ";-1"
        sel_end = 0

        rename_config_substr = RenameConfig("substr")
        if 0 < len(last := rename_config_substr.value):
            placeholder = last
            sel_end = last.find(";")

        print("Rename substring (extract part of filename):")
        rename_command = stringify(
            window.commandLine(
                "Offset[;Length]", text=placeholder, selection=[0, sel_end]
            )
        )

        if len(rename_command) < 1:
            print("Canceled.\n")
            return

        sep = ";"
        if sep not in rename_command:
            rename_command += ";-1"
        else:
            if rename_command.startswith(sep):
                rename_command = "0" + rename_command

        offset = int(rename_command[: rename_command.find(sep)])
        length = int(rename_command[rename_command.rfind(sep) + 1 :])

        if offset == 0 and length == -1:
            print("Canceled.\n")
            return

        rename_config_substr.register(rename_command)

        def _confirm() -> tuple[list[RenameInfo], bool]:
            infos = []
            lines = []
            for item in targets:
                org_path = Path(item.getFullpath())

                def _get_new_stem() -> str:
                    stem = org_path.stem
                    if length < 0:
                        if length == -1:
                            return stem[offset:]
                        return stem[offset : length + 1]
                    return stem[offset : offset + length]

                new_name = _get_new_stem() + org_path.suffix
                infos.append(RenameInfo(org_path, new_name))
                lines.append(f"Rename: {org_path.name}\n    ==> {new_name}\n")

            lines.append(f"\noffset: {offset}\nlength: {length}\nOK? (Enter / Esc)")

            return infos, popResultWindow(window, "Preview", "\n".join(lines))

        infos, ok = _confirm()
        if len(infos) < 1 or not ok:
            print("Canceled.\n")
            return

        krtr = kiritori
        krtr.draw_header("Renaming:")
        [renamer.execute(info.orgPath, info.newName) for info in infos]
        krtr.draw_footer()

    keybinder.bind(rename_substr, "S-S")

    def rename_insert() -> None:
        renamer = Renamer()

        targets = renamer.candidate
        if len(targets) < 1:
            return

        placeholder = "@-1"
        sel_end = 0

        rename_config_insert = RenameConfig("insert")
        last_insert = rename_config_insert.value
        if 0 < len(last_insert):
            placeholder = last_insert
            sel_end = last_insert.find("@")

        print("Rename insert:")
        rename_command = stringify(
            window.commandLine(
                "Text[@position]", text=placeholder, selection=[0, sel_end]
            ),
            False,
        ).rstrip()

        if len(rename_command) < 1:
            print("Canceled.\n")
            return

        sep = "@"
        if rename_command.startswith(sep):
            print("Canceled.\n")
            return

        if sep not in rename_command:
            rename_command += "@-1"
        else:
            if rename_command.endswith(sep):
                rename_command += "-1"

        rename_config_insert.register(rename_command)

        ins = rename_command[: rename_command.rfind(sep)]
        pos = int(rename_command[rename_command.rfind(sep) + 1 :])

        def _confirm() -> tuple[list[RenameInfo], bool]:
            infos = []
            lines = []
            for item in targets:
                org_path = Path(item.getFullpath())

                def _get_new_stem() -> str:
                    stem = org_path.stem
                    if pos < 0:
                        if pos == -1:
                            return stem + ins
                        p = pos + 1
                        return stem[:p] + ins + stem[p:]
                    return stem[:pos] + ins + stem[pos:]

                new_name = _get_new_stem() + org_path.suffix
                infos.append(RenameInfo(org_path, new_name))
                lines.append(f"Rename: {org_path.name}\n    ==> {new_name}\n")

            lines.append(f"\ninsert: {ins}\nat: {pos}\nOK? (Enter / Esc)")

            return infos, popResultWindow(window, "Preview", "\n".join(lines))

        infos, ok = _confirm()
        if len(infos) < 1 or not ok:
            print("Canceled.\n")
            return

        krtr = kiritori
        krtr.draw_header("Renaming:")
        [renamer.execute(info.orgPath, info.newName) for info in infos]
        krtr.draw_footer()

    keybinder.bind(rename_insert, "S-I")

    class PhotoFile:
        def __init__(self, path: str):
            self.path = path
            _, self.name = os.path.split(self.path)
            _, self.ext = os.path.splitext(self.name)
            self.filler = datetime.datetime.fromtimestamp(0)

        def get_byte_offset(self) -> int:
            ext = self.ext.lower()[1:]
            if ext in ["jpeg", "jpg", "webp"]:
                return 0
            if ext == "raf":
                if self.name.startswith("_DSF"):
                    return 0x19E
                return 0x17A
            if ext == "cr2":
                return 0x144
            if self.name.startswith("MVI_") and ext == "mp4":
                return 0x160
            return -1

        def from_exif(self) -> datetime.datetime:
            try:
                with PILImage.open(self.path) as img:
                    exif_data = img._getexif()
                    if not exif_data:
                        return self.filler
                    for tag_id, value in exif_data.items():
                        tag = TAGS.get(tag_id, tag_id)
                        if tag == "DateTimeOriginal":
                            dt = datetime.datetime.strptime(value, "%Y:%m:%d %H:%M:%S")
                            return dt
                    return self.filler
            except Exception as e:
                print(e)
                return self.filler

        def get_timestamp(self) -> datetime.datetime:
            offset = self.get_byte_offset()
            if offset < 1:
                if offset == 0:
                    return self.from_exif()
                return self.filler
            with open(self.path, "rb") as f:
                f.seek(offset)
                bytes_read = f.read(19)
            decoded = bytes_read.decode("ascii")
            return datetime.datetime.strptime(decoded, "%Y:%m:%d %H:%M:%S")

        def rename(self, fmt: str) -> str:
            ts = self.get_timestamp().strftime(fmt)
            return ts + "_" + self.name

    def rename_photo_file_by_exifdate() -> None:
        renamer = Renamer()

        targets = []
        for item in renamer.candidate:
            if not item.isdir():
                targets.append(item)

        if len(targets) < 1:
            return

        def _confirm() -> tuple[list[RenameInfo], bool]:
            infos = []
            lines = []
            for item in targets:
                path = item.getFullpath()
                photo = PhotoFile(path)
                new_name = photo.rename("%Y_%m%d_%H%M%S00")
                infos.append(RenameInfo(Path(path), new_name))
                lines.append(f"Rename: {item.getName()}\n    ==> {new_name}\n")

            lines.append("\ninsert timestamp:\nOK? (Enter / Esc)")

            return infos, popResultWindow(window, "Preview", "\n".join(lines))

        infos, ok = _confirm()
        if len(infos) < 1 or not ok:
            print("Canceled.\n")
            return

        krtr = kiritori
        krtr.draw_header("Renaming:")
        [renamer.execute(info.orgPath, info.newName) for info in infos]
        krtr.draw_footer()

    def rename_lightroom_photo_from_dropbox() -> None:
        renamer = Renamer()

        targets = []
        for item in renamer.candidate:
            if not item.isdir():
                targets.append(item)

        if len(targets) < 1:
            return

        def _confirm() -> tuple[list[RenameInfo], bool]:
            infos = []
            lines = []
            for item in targets:
                path = item.getFullpath()
                p = Path(path)
                elems = p.stem.replace("写真 ", "").split(" ")
                date_ts = elems[0].replace("-", "")
                time_ts = "".join([str(n).rjust(2, "0") for n in elems[1:4]])
                if 4 < len(elems):
                    time_ts = (
                        time_ts + "-" + elems[-1].replace("(", "").replace(")", "")
                    )
                new_name = date_ts + "-IMG_" + time_ts + p.suffix
                infos.append(RenameInfo(p, new_name))
                lines.append(f"Rename: {item.getName()}\n    ==> {new_name}\n")

            lines.append("\ninsert timestamp:\nOK? (Enter / Esc)")

            return infos, popResultWindow(window, "Preview", "\n".join(lines))

        infos, ok = _confirm()
        if len(infos) < 1 or not ok:
            print("Canceled.\n")
            return

        krtr = kiritori
        krtr.draw_header("Renaming:")
        [renamer.execute(info.orgPath, info.newName) for info in infos]
        krtr.draw_footer()

    def rename_index() -> None:
        renamer = Renamer()

        targets = renamer.candidate
        if len(targets) < 1:
            return

        placeholder = "01@-1,1;_;"
        rename_config_index = RenameConfig("index")
        last_value = rename_config_index.value
        if 0 < len(last_value):
            placeholder = last_value

        print("Rename insert index:")
        rename_command = stringify(
            window.commandLine(
                "Index[@position,step,skips1,skips2,...;connector;newstem]",
                text=placeholder,
                selection=[0, 2],
            ),
            trim=False,
        )

        if len(rename_command) < 1:
            print("Canceled.\n")
            return

        sep = ";"
        if sep not in rename_command:
            rename_command += sep * 2
        else:
            if len(rename_command.split(sep)) < 3:
                rename_command += sep

        command_index, connector, command_newstem = rename_command.split(sep)[:3]

        class NameIndex:
            position = -1
            step = 1
            skips = []

            def __init__(self) -> None:
                commands = command_index.split("@")
                left_parts = commands[0].rstrip()
                if str(left_parts).isdecimal():
                    self.index_template = left_parts
                else:
                    self.index_template = "00"
                if 1 < len(commands):
                    args = [a.strip() for a in commands[1].split(",")]
                    self.position = int(args[0])
                    if 1 < len(args):
                        self.step = int(args[1])
                    if 2 < len(args):
                        self.skips = [int(a) for a in args[2:]]

                c = self.index_template[0]
                if c in "123456789":
                    self.filler = ""
                else:
                    self.filler = c

            def fill(self, i: int) -> str:
                s = str(i)
                w = len(self.index_template)
                filled = s if len(self.filler) < 1 else s.rjust(w, self.filler)
                if self.position < 0:
                    return connector + filled
                return filled + connector

            @property
            def start(self) -> int:
                return int(self.index_template)

            def increment(self, i: int) -> int:
                i += self.step
                while 1:
                    if i not in self.skips:
                        break
                    i += self.step
                return i

        ni = NameIndex()

        print(rename_command)
        rename_config_index.register(rename_command)

        def _confirm() -> tuple[list[RenameInfo], bool]:
            infos = []
            lines = []
            idx = ni.start
            for item in targets:
                org_path = Path(item.getFullpath())
                stem = org_path.stem if len(command_newstem) < 1 else command_newstem
                pos = ni.position
                if ni.position < 0:
                    pos = len(stem) + 1 + ni.position
                new_name = stem[:pos] + ni.fill(idx) + stem[pos:] + org_path.suffix
                idx = ni.increment(idx)
                infos.append(RenameInfo(org_path, new_name))
                lines.append(f"Rename: {org_path.name}\n    ==> {new_name}\n")

            lines.append(
                f"\ninsert (start={ni.start}, step={ni.step}, skips={ni.skips}):\nOK? (Enter / Esc)"
            )

            return infos, popResultWindow(window, "Preview", "\n".join(lines))

        infos, ok = _confirm()
        if len(infos) < 1 or not ok:
            print("Canceled.\n")
            return

        krtr = kiritori
        krtr.draw_header("Renaming:")
        [renamer.execute(info.orgPath, info.newName) for info in infos]
        krtr.draw_footer()

    keybinder.bind(rename_index, "A-S-I")

    def rename_regexp() -> None:
        renamer = Renamer()

        targets = renamer.candidate
        if len(targets) < 1:
            return

        placeholder = "/"
        sel_end = 0

        rename_config_regexp = RenameConfig("regexp")
        last_regexp = rename_config_regexp.value
        if 0 < len(last_regexp):
            placeholder = last_regexp
            sel_end = max(last_regexp.find("/"), 0)

        print("Rename with regexp-replace. Trailing `/c` enables case-sensitive-mode")
        rename_command = window.commandLine(
            "[regexp]/[replace with](/c)", text=placeholder, selection=[0, sel_end]
        )

        if not rename_command:
            print("Canceled.\n")
            return

        class RegCommand:
            sep = "/"

            def __init__(self, line: str) -> None:
                a = line.split(self.sep)
                if len(a) < 2:
                    a.append("")
                if len(a) < 3:
                    a.append("")
                self.args = a

            def is_valid(self) -> bool:
                return 0 < len(self.args[0])

            @property
            def search_reg(self) -> re.Pattern:
                r = self.args[0]
                if self.args[2] == "c":
                    return re.compile(r)
                return re.compile(r, re.IGNORECASE)

            @property
            def to_str(self) -> str:
                return self.args[1]

        rc = RegCommand(rename_command)
        if not rc.is_valid():
            print("Canceled (Invalid command).\n")
            return

        rename_config_regexp.register(rename_command)
        reg = rc.search_reg

        def _confirm() -> tuple[list[RenameInfo], bool]:
            infos = []
            lines = []
            for item in targets:
                org_path = Path(item.getFullpath())
                new_name = reg.sub(rc.to_str, org_path.stem) + org_path.suffix
                if org_path.name != new_name:
                    infos.append(RenameInfo(org_path, new_name))
                    lines.append(f"Rename: {org_path.name}\n    ==> {new_name}\n")

            if len(lines) < 1:
                lines.append("Nothing will be renamed.")
            else:
                lines.append(
                    f"\nregexp: {reg}\nnew text: {rc.to_str}\nOK? (Enter / Esc)"
                )

            return infos, popResultWindow(window, "Preview", "\n".join(lines))

        infos, ok = _confirm()
        if len(infos) < 1 or not ok:
            print("Canceled.\n")
            return

        krtr = kiritori
        krtr.draw_header("Renaming:")
        [renamer.execute(info.orgPath, info.newName) for info in infos]
        krtr.draw_footer()

    keybinder.bind(rename_regexp, "S-R")

    class NameAffix:
        sep = "_"

        def __init__(self) -> None:
            self.pane = CPane()

        @staticmethod
        def to_stem(path: str) -> str:
            _, name = os.path.split(path)
            stem, _ = os.path.splitext(name)
            return stem

        def selected_stems(self) -> list[str]:
            sels = self.pane.selectedItemPaths + CPane(False).selectedItemPaths
            return sorted([self.to_stem(sel) for sel in sels])

        @staticmethod
        def len_ordered_unify(lines: list[str]) -> list[str]:
            return [str(s) for s in sorted(set(lines), key=len)]

    class NamePrefix(NameAffix):
        def __init__(self) -> None:
            super().__init__()

        @classmethod
        def from_name(cls, s: str) -> list[str]:
            pres = []
            for i, c in enumerate(s):
                if 0 < i and c == cls.sep:
                    pres.append(s[: i + 1])
            return pres

        def variants(self) -> list[str]:
            pres = []
            for path in self.pane.paths:
                pres += self.from_name(self.to_stem(path))
            return pres

    class PrefixHandler(NamePrefix):
        def __init__(self) -> None:
            super().__init__()
            self.candidates = self.variants()
            self.selected = self.selected_stems()

        def filter_by(self, s: str) -> list[str]:
            return [pre for pre in self.candidates if pre.startswith(s)]

        def invoke(
            self,
        ) -> Callable[[ckit.ckit_widget.EditWidget.UpdateInfo], tuple[list[str], int]]:
            def _handler(
                update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
            ) -> tuple[list[str], int]:
                found = self.filter_by(update_info.text)
                return self.selected + self.len_ordered_unify(found), 0

            return _handler

    class NameSuffix(NameAffix):
        def __init__(
            self,
            with_timestamp: bool = False,
            additional: list[str] = [],
        ) -> None:
            super().__init__()
            self.timestamp = ""
            if with_timestamp:
                self.timestamp = datetime.datetime.today().strftime("%Y%m%d")

            self._additional = [self.sep + a for a in additional]

        @classmethod
        def from_name(cls, s: str) -> list[str]:
            sufs = []
            for i, c in enumerate(s):
                if 0 < i and c == cls.sep:
                    sufs.append(s[i:])
            return sufs

        def variants(self) -> list[str]:
            sufs = []
            for path in self.pane.paths:
                sufs += self.from_name(self.to_stem(path))
            if 0 < len(self._additional):
                sufs += self._additional
            if self.timestamp:
                if (s := self.sep + self.timestamp) not in sufs:
                    sufs = [s] + sufs
            return sufs

        def from_parents(self) -> list[str]:
            found = []
            parents = Path(self.pane.currentPath, "_").parents
            reg = re.compile(r"[0-9]{6,}")
            for parent in parents:
                if m := reg.search(parent.name):
                    found.append(self.sep + m.group(0))
                    break
            return found

    class SuffixHandler(NameSuffix):
        def __init__(self, with_timestamp: bool = False, additional: list[str] = []):
            super().__init__(with_timestamp, additional)
            self.selected = self.selected_stems()
            self.candidates = self.variants() + self.from_parents()

        def filter_by(self, s: str) -> list[str]:
            suffixes = self.candidates
            if self.sep not in s:
                return [s + suf for suf in suffixes]
            if s.endswith(self.sep):
                return [s + suf[1:] for suf in suffixes]
            found = []
            sep_pos = s.find(self.sep)
            command_suffix = s[sep_pos:]
            for suf in suffixes:
                if suf.startswith(command_suffix):
                    found.append(s[:sep_pos] + suf)
            return found

        def invoke(
            self,
        ) -> Callable[[ckit.ckit_widget.EditWidget.UpdateInfo], tuple[list[str], int]]:
            def _filter(
                update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
            ) -> tuple[list[str], int]:
                found = self.filter_by(update_info.text)
                return self.selected + self.len_ordered_unify(found), 0

            return _filter

    def name_candidate_handler(
        with_timestamp: bool,
    ) -> Callable[[ckit.ckit_widget.EditWidget.UpdateInfo], tuple[list[str], int]]:
        prefix_handler = PrefixHandler()
        suffix_handler = SuffixHandler(with_timestamp)
        selected = NameAffix().selected_stems()

        def _handler(
            update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
        ) -> tuple[list[str], int]:
            s = update_info.text
            found = (
                prefix_handler.filter_by(s)
                if NameAffix.sep not in s
                else suffix_handler.filter_by(s)
            )

            return selected + NameAffix.len_ordered_unify(found), 0

        return _handler

    def rename_stem() -> None:
        pane = CPane()
        if pane.isBlank:
            return
        item = pane.focusedItem

        renamer = Renamer()
        if not renamer.renamable(item):
            return

        ts = item.time()
        item_timestamp = f"{ts[0]}{ts[1]:02}{ts[2]:02}"
        additional_suffix = [item_timestamp]

        focused_path = Path(item.getFullpath())
        placeholder = focused_path.name if focused_path.is_dir() else focused_path.stem
        offset = len(placeholder)
        sel = [offset, offset]

        new_stem, mod = window.commandLine(
            title="NewStem",
            text=placeholder,
            selection=sel,
            candidate_handler=SuffixHandler(True, additional_suffix).invoke(),
            return_modkey=True,
        )

        new_stem = stringify(new_stem)
        if len(new_stem) < 1:
            return

        new_name = new_stem
        if not focused_path.is_dir():
            new_name += focused_path.suffix

        krtr = kiritori
        krtr.draw_header("Renaming:")
        renamer.execute(focused_path, new_name, mod == ckit.MODKEY_SHIFT)
        krtr.draw_footer()

    keybinder.bind(rename_stem, "N")

    def rename_ext() -> None:
        pane = CPane()
        if pane.isBlank:
            return
        item = pane.focusedItem
        if item.isdir():
            return

        renamer = Renamer()
        if not renamer.renamable(item) or pane.isBlank:
            return

        focused_path = Path(item.getFullpath())
        placeholder = focused_path.suffix

        exts = []
        for item in pane.items:
            name = item.getName()
            _, ext = os.path.splitext(name)
            if 0 < len(ext):
                exts.append(ext)
        exts = sorted(list(set(exts)))

        def _listup_exts(
            update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
        ) -> tuple:
            found = []
            for ext in exts:
                if ext.lower().startswith(update_info.text.lower()):
                    found.append(ext)
            return found, 0

        new_ext, mod = window.commandLine(
            title="NewExt",
            text=placeholder,
            selection=[1, len(placeholder)],
            candidate_handler=_listup_exts,
            return_modkey=True,
        )

        new_ext = stringify(new_ext)

        new_name = focused_path.stem + new_ext

        krtr = kiritori
        krtr.draw_header("Renaming:")
        renamer.execute(focused_path, new_name, mod == ckit.MODKEY_SHIFT)
        krtr.draw_footer()

    keybinder.bind(rename_ext, "S-N")

    def multiple_selected_item() -> None:
        pane = CPane()
        if not pane.hasSelection:
            return
        if 1 < len(pane.selectedItems):
            kiritori.log("Caneled. (Select just 1 item)")
            return

        src_path = Path(pane.selectedItemPaths[0])
        result = stringify(
            window.commandLine(
                title="connector,suffix,count",
                text="-,01,2",
            )
        )

        if len(result) < 1:
            return

        elems = result.split(",")
        if len(elems) < 3:
            if len(elems) < 2:
                elems.append("0")
            elems.append("1")
        [connector, template, count] = elems
        if len(template.strip()) < 1 or len(count.strip()) < 1:
            return
        if not template[-1].isdecimal() or not count.strip().isdecimal():
            kiritori.log("Invalid format.")
            return

        count = int(count.strip())
        if count < 1:
            return

        def _clone(src: Path, conn: str, temp: str, cnt: int) -> None:
            for i in range(int(temp), cnt + 1):
                w = len(temp)
                n = str(i)
                tail = n.rjust(w, temp[0]) if 1 < w else n.rjust(w)
                new_path = src.with_name(src.stem + conn + tail + src.suffix)
                if smart_check_path(new_path):
                    print(f"Skipped because of name dupl: {new_path.name}")
                else:
                    if src.is_dir():
                        shutil.copytree(src, new_path)
                    else:
                        shutil.copy(src, new_path)
                    print(f"Cloned: {new_path.name}")

        krtr = kiritori
        krtr.draw_header("Making clone:")
        window.subThreadCall(_clone, (src_path, connector, template, count))
        pane.refresh()
        krtr.draw_footer()

    keybinder.bind(multiple_selected_item, "C-S-C")

    def duplicate_with_new_stem() -> None:
        pane = CPane()

        src_path = Path(pane.focusedItemPath)
        if pane.hasSelection:
            if 1 < len(pane.selectedItems):
                kiritori.log("Caneled. (Select nothing or just 1 item)")
                return
            src_path = Path(pane.selectedItemPaths[0])

        sel_end = len(src_path.stem)
        sel_start = src_path.stem.rfind("_")
        if sel_start < 0:
            sel_start = sel_end
        prompt = "NewStem"
        placeholder = src_path.stem
        result = stringify(
            window.commandLine(
                title=prompt,
                text=placeholder,
                candidate_handler=SuffixHandler(True).invoke(),
                selection=[sel_start, sel_end],
            )
        )

        if len(result) < 1:
            return

        if src_path.is_file():
            result = result + src_path.suffix
        new_path = src_path.with_name(result)

        if smart_check_path(new_path):
            kiritori.log("Canceled. (Same item exists)")
            return

        def _copy_as(new_path: str) -> None:
            if src_path.is_dir():
                shutil.copytree(src_path, new_path)
            else:
                shutil.copy(src_path, new_path)

        window.subThreadCall(_copy_as, (new_path,))
        pane.refresh()
        pane.focusByName(new_path.name)

    keybinder.bind(duplicate_with_new_stem, "S-D")

    def duplicate_with_new_extension() -> None:
        pane = CPane()

        src_path = Path(pane.focusedItemPath)
        if pane.hasSelection:
            if 1 < len(pane.selectedItems):
                kiritori.log("Caneled. (Select nothing or just 1 item)")
                return
            src_path = Path(pane.selectedItemPaths[0])

        if src_path.is_dir():
            kiritori.log("Caneled. (Dirctory has no extension)")
            return

        sel_start = len(src_path.stem) + 1
        sel_end = len(src_path.name)
        prompt = "NewName"
        result = stringify(
            window.commandLine(
                title=prompt,
                text=src_path.name,
                selection=[sel_start, sel_end],
            )
        )

        if len(result) < 1:
            return

        new_path = src_path.with_name(result)

        if smart_check_path(new_path):
            kiritori.log("Canceled. (Same item exists)")
            return

        def _copy_as(new_path: str) -> None:
            shutil.copy(src_path, new_path)

        window.subThreadCall(_copy_as, (new_path,))
        pane.refresh()
        pane.focusByName(new_path.name)

    keybinder.bind(duplicate_with_new_extension, "A-S-D")

    def smart_copy_to_dir(remove_origin: bool) -> None:
        prompt = "MoveTo" if remove_origin else "CopyTo"

        pane = CPane()

        items = []
        for item in pane.selectedItems:
            if remove_origin and not hasattr(item, "delete"):
                continue
            items.append(item)

        if len(items) < 1:
            pane.select(pane.cursor)
            return

        dests = []
        for item in pane.items:
            if item.isdir() and not item.selected():
                name = item.getName()
                if name not in dests:
                    dests.append(name)

        obs_name = "_obsolete"
        if obs_name not in dests:
            dests.append(obs_name)

        def _listup_dests(
            update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
        ) -> tuple:
            found = [
                dest
                for dest in dests
                if dest.lower().startswith(update_info.text.lower())
            ]
            return found, 0

        placeholder = "" if len(pane.dirs) != 1 else pane.dirs[0].getName()
        result, mod = window.commandLine(
            prompt,
            text=placeholder,
            candidate_handler=_listup_dests,
            return_modkey=True,
        )

        result = stringify(result)
        if len(result) < 1:
            return

        dir_path = os.path.join(pane.currentPath, result)
        if not smart_check_path(dir_path):
            pane.mkdir(result)
        pane.copyToChild(result, items, remove_origin)
        if mod == ckit.MODKEY_SHIFT:
            pane.openPath(dir_path)
        else:
            pane.focusByName(result)

    keybinder.bind(lambda: smart_copy_to_dir(True), "S-M")
    keybinder.bind(lambda: smart_copy_to_dir(False), "S-C")

    def smart_mkdir() -> None:
        pane = CPane()
        ts = datetime.datetime.today().strftime("%Y%m%d")
        result, mod = window.commandLine(
            "DirName",
            text=ts,
            selection=[0, len(ts)],
            candidate_handler=name_candidate_handler(False),
            return_modkey=True,
        )

        dirname = stringify(result)
        if len(dirname) < 1:
            return
        pane.mkdir(dirname)
        if mod == ckit.MODKEY_SHIFT:
            pane.openChild(dirname)

    keybinder.bind(smart_mkdir, "C-S-N")

    def touch_new_file() -> None:
        pane = CPane()
        if not hasattr(pane.fileList.getLister(), "touch"):
            return

        result, mod = window.commandLine(
            "Stem",
            candidate_handler=name_candidate_handler(True),
            return_modkey=True,
        )

        stem = stringify(result)
        if len(stem) < 1:
            return

        if "." in stem:
            ext = ""
        else:
            exts = ["txt", "md", "css", "html"]

            def _listup_exts(
                update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
            ) -> tuple:
                found = [
                    ext
                    for ext in exts
                    if ext.lower().startswith(update_info.text.lower())
                ]
                return found, 0

            ext = window.commandLine(
                "Extension",
                text=exts[0],
                selection=[0, len(exts[0])],
                candidate_handler=_listup_exts,
                auto_complete=True,
            )

            if ext is None:
                return
            if len(ext) < 1:
                ext = exts[0]
            ext = "." + ext

        new_name = stem + ext
        new_path = os.path.join(pane.currentPath, new_name)
        if smart_check_path(new_path):
            kiritori.log(f"'{stem}' already exists.")
            return

        pane.touch(new_name)
        if mod == ckit.MODKEY_SHIFT:
            shell_exec(new_path)

    keybinder.bind(touch_new_file, "T")

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

    keybinder.bind(to_home_position, "C-0")

    class sorter_UnderscoreFirst:
        def __init__(self, order: int = 1) -> None:
            self.order = order

        def __call__(self, items) -> None:
            def _sort_key(item) -> tuple:
                dir_upper_flag = not item.isdir() if self.order == 1 else item.isdir()
                name = item.getName()
                stem, ext = os.path.splitext(name)
                underscore_count = len(name) - len(name.lstrip("_"))
                return (
                    dir_upper_flag,
                    not name.startswith("."),
                    not name.startswith("_"),
                    (-1 * underscore_count),
                    stem.lower(),
                    ext.lower(),
                )

            items.sort(key=_sort_key, reverse=self.order == -1)

    def setup_sorter() -> None:
        if len(window.sorter_list) == 4:
            window.sorter_list = [
                (
                    "U : Underscore Order",
                    sorter_UnderscoreFirst(),
                    sorter_UnderscoreFirst(order=-1),
                ),
            ] + window.sorter_list

        sorter = window.sorter_list[0][1]
        LeftPane().setSorter(sorter)
        RightPane().setSorter(sorter)

    setup_sorter()

    def reload_config() -> None:
        window.configure()
        ts = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S.%f")
        window.setStatusMessage(f"Reloaded config.py | {ts}", 2000)

    keybinder.bind(reload_config, "C-R", "F5")

    def open_desktop_to_other() -> None:
        pane = CPane()
        other = CPane(False)
        if DESKTOP_PATH not in [pane.currentPath, other.currentPath]:
            other.openPath(DESKTOP_PATH)
        pane.focusOther()

    keybinder.bind(open_desktop_to_other, "A-O")

    def starting_position(both_pane: bool = False) -> None:
        window.command_MoveSeparatorCenter(None)
        pane = CPane()
        if pane.currentPath != DESKTOP_PATH:
            pane.openPath(DESKTOP_PATH)
        if both_pane:
            window.command_ChdirInactivePaneToOther(None)
            LeftPane().activate()

    keybinder.bind(lambda: starting_position(False), "0")
    keybinder.bind(lambda: starting_position(True), "S-0")

    def safe_quit() -> None:
        if window.ini.getint("MISC", "confirm_quit"):
            result = cfiler_msgbox.popMessageBox(
                window,
                cfiler_msgbox.MessageBox.TYPE_YESNO,
                "Confirm",
                "Quit?",
            )
            if result != cfiler_msgbox.MessageBox.RESULT_YES:
                return

        left = LeftPane()
        right = RightPane()
        for pane in [left, right]:
            if not pane.currentPath.startswith("C:"):
                pane.openPath(DESKTOP_PATH)

        window.quit()

    keybinder.bind(safe_quit, "C-Q", "A-F4")

    def open_doc() -> None:
        shell_exec("https://github.dev/crftwr/cfiler/blob/master/cfiler_mainwindow.py")

    keybinder.bind(open_doc, "C-F1")

    def edit_config() -> None:
        config_dir = os.path.join(os.environ.get("APPDATA", ""), "CraftFiler")
        if not smart_check_path(config_dir):
            kiritori.log(f"cannot find config dir: {config_dir}")
            return
        dir_path = config_dir
        if (real_path := os.path.realpath(config_dir)) != config_dir:
            dir_path = os.path.dirname(real_path)

        result = open_vscode(dir_path)
        if not result:
            subprocess.run(["explorer.exe", dir_path])

    keybinder.bind(edit_config, "C-E")

    def make_shortcut() -> None:
        pane = CPane()
        target = pane.selectedItemNames
        if len(target) < 1:
            target.append(pane.focusedItem.getName())

        other_pane_dir = CPane(False).currentPath
        for name in target:
            lnk_path = str(Path(other_pane_dir, name).with_suffix(".lnk"))
            src_path = str(Path(pane.currentPath, name))
            run_ps1("mklnk", src_path, lnk_path)
            kiritori.log(f"Created shortcut '{lnk_path}'")

    class FileHashDiff:
        def __init__(self, max_mb: int):
            self.max_mb = max_mb

        @staticmethod
        def count_bytes(s: str) -> int:
            n = 0
            for c in s:
                if unicodedata.east_asian_width(c) in "FWA":
                    n += 2
                else:
                    n += 1
            return n

        def to_hash(self, path: str) -> str:
            mb = 1024 * 1024
            read_size = 1 * mb if self.max_mb * mb < os.path.getsize(path) else None
            with open(path, "rb") as f:
                digest = hashlib.md5(f.read(read_size)).hexdigest()
            return digest

        def progress(self, name: str) -> None:
            print(f"checking first {self.max_mb}MB of: {name}")

        def compare(self) -> None:
            pane = CPane()
            other_pane = CPane(False)
            with_selection = other_pane.hasSelection
            _, dirname = os.path.split(pane.currentPath)
            _, other_dirname = os.path.split(other_pane.currentPath)

            krtr = kiritori

            def _scan(job_item: ckit.JobItem) -> None:
                targets = []
                for item in pane.selectedOrAllItems:
                    pane.unSelectByName(item.getName())
                    if not item.isdir():
                        targets.append(item)

                if len(targets) < 1:
                    return

                krtr.draw_header("Comparing md5 hash:")

                window.setProgressValue(None)

                table = {}
                exts = set()

                for file in targets:
                    if job_item.isCanceled():
                        return
                    path = file.getFullpath()
                    digest = self.to_hash(path)
                    _, name = os.path.split(path)
                    _, ext = os.path.splitext(name)
                    self.progress(dirname + os.sep + name)
                    table[digest] = table.get(digest, []) + [name]
                    exts.add(ext)

                def __files_to_compare() -> (
                    Iterator[ItemDefaultProtocol] | list[ItemDefaultProtocol]
                ):
                    if with_selection:
                        sels = other_pane.selectedItems
                        other_pane.unSelectAll()
                        return sels
                    return other_pane.traverse(True)

                clones: dict[str, list[str]] = {}

                for item in __files_to_compare():
                    if job_item.isCanceled():
                        return
                    path = item.getFullpath()
                    _, ext = os.path.splitext(path)
                    if ext not in exts:
                        continue
                    rel = os.path.relpath(path, other_pane.currentPath)
                    self.progress(other_dirname + os.sep + rel)
                    digest = self.to_hash(path)
                    if digest in table:
                        names = table[digest]
                        for name in names:
                            clones[name] = clones.get(name, []) + [rel]

                job_item.clones = clones

            def _finish(job_item: ckit.JobItem) -> None:
                window.clearProgress()
                if job_item.isCanceled():
                    print("\nCanceled.")
                else:
                    print("\nFinished.\n")
                    if not job_item.clones or len(job_item.clones) < 1:
                        print("(There was no clone)")
                    else:
                        for name, clone_names in job_item.clones.items():
                            pane.selectByName(name)
                            other_pane.selectByNames(
                                [n for n in clone_names if os.sep not in n]
                            )

                            filler = " " * self.count_bytes(name)
                            for i, n in enumerate(clone_names):
                                if i == 0:
                                    print(name, "==", n)
                                else:
                                    print(filler, "==", n)
                    krtr.draw_footer()

            job = ckit.JobItem(_scan, _finish)
            window.taskEnqueue(job, create_new_queue=False)

    def diff_files(with_diffinity: bool) -> None:
        pane = CPane()
        left_path = ""
        right_path = ""

        if (
            pane.hasSelection
            and len(pane.selectedItems) == 2
            and not CPane(False).hasSelection
        ):
            left_path, right_path = pane.selectedItemPaths
        else:
            left_pane = LeftPane()
            right_pane = RightPane()
            if len(left_pane.selectedItems) == 1 and len(right_pane.selectedItems) == 1:
                left_path = left_pane.selectedItemPaths[0]
                right_path = right_pane.selectedItemPaths[0]

        if not left_path or not right_path:
            kiritori.log(
                "Select 1 item for each pane or 2 items in one pane to compare."
            )
            return

        if with_diffinity:
            exe_path = shutil.which("Diffinity")
            if exe_path is None:
                kiritori.log("cannnot find diffinity.exe...")
                return

            exe_path = resolve_scoop_shim(exe_path)
            shell_exec(exe_path, left_path, right_path)
            return

        exe_path = shutil.which("code")
        if exe_path is None:
            kiritori.log("cannnot find vscode...")
            return

        def _open_code(_) -> None:
            open_vscode(
                "--new-window",
                "--disable-extensions",
                "--diff",
                left_path,
                right_path,
            )

        job = ckit.JobItem(_open_code, lambda _: None)
        window.taskEnqueue(job, create_new_queue=False)

    def from_other_names() -> None:
        pane = CPane()
        pane.unSelectAll()
        active_names = pane.names
        other = CPane(False)
        other_names = [item.getName() for item in other.selectedOrAllItems]
        for name in active_names:
            if name in other_names:
                pane.selectByName(name)

    def from_active_names() -> None:
        pane = CPane()
        active_names = [item.getName() for item in pane.selectedOrAllItems]
        other = CPane(False)
        other.unSelectAll()
        other_names = other.names
        for name in other_names:
            if name in active_names:
                other.selectByName(name)

    def invoke_regex_selector(case: bool) -> CallbackFunc:
        def _selector() -> None:
            result, mod = window.commandLine("Regexp", return_modkey=True)

            if result:
                selector.stem_matches(result, case, mod == ckit.MODKEY_SHIFT)

        return _selector

    keybinder.bind(invoke_regex_selector(True), "S-Colon")

    def select_same_name() -> None:
        pane = CPane()
        active_names = pane.selectedItemNames
        if len(active_names) < 1:
            active_names = [pane.focusedItem.getName()]
        other = CPane(False)
        other.unSelectAll()

        for name in other.names:
            if name in active_names:
                other.selectByName(name)

    def select_name_common() -> None:
        pane = CPane()
        pane.unSelectAll()
        active_names = pane.names
        other = CPane(False)
        other.unSelectAll()
        other_names = other.names

        for name in active_names:
            if name in other_names:
                pane.selectByName(name)
        for name in other_names:
            if name in active_names:
                other.selectByName(name)

    def select_name_unique() -> None:
        pane = CPane()
        pane.unSelectAll()
        active_names = pane.names
        other = CPane(False)
        other.unSelectAll()
        other_names = other.names

        for name in active_names:
            if name not in other_names:
                pane.selectByName(name)
        for name in other_names:
            if name not in active_names:
                other.selectByName(name)

    def select_stem_startswith() -> None:
        result, mod = window.commandLine(
            "StartsWith",
            return_modkey=True,
            candidate_handler=PrefixHandler().invoke(),
        )
        if result:
            selector.stem_starts_with(result, mod == ckit.MODKEY_SHIFT)

    keybinder.bind(select_stem_startswith, "Caret")

    def select_stem_endswith() -> None:
        result, mod = window.commandLine(
            "EndsWith",
            return_modkey=True,
            candidate_handler=SuffixHandler().invoke(),
        )
        if result:
            selector.stem_ends_with(result, mod == ckit.MODKEY_SHIFT)

    keybinder.bind(select_stem_endswith, "S-4")

    def select_stem_contains() -> None:
        result, mod = window.commandLine("Contains", return_modkey=True)
        if result:
            selector.stem_contains(result, mod == ckit.MODKEY_SHIFT)

    keybinder.bind(select_stem_contains, "Colon")

    def select_byext() -> None:
        pane = CPane()
        exts = []
        for item in pane.selectedOrAllItems:
            ext = Path(item.getFullpath()).suffix[1:]
            if ext and ext not in exts:
                exts.append(ext)

        if len(exts) < 1:
            return

        result, mod = invoke_listwindow("Select Extension", exts)

        if result < 0:
            return

        selector.by_extension("." + exts[result], mod == ckit.MODKEY_SHIFT)

    keybinder.bind(select_byext, "S-X")

    class PseudoVoicing:
        voicables = "かきくけこさしすせそたちつてとはひふへほカキクケコサシスセソタチツテトハヒフヘホ"

        def __init__(self, s) -> None:
            self._formatted = s

        def _replace(self, s: str, offset: int) -> str:
            c = s[0]
            if c not in self.voicables:
                return s
            if offset == 1:
                if c == "う":
                    return "\u3094"
                if c == "ウ":
                    return "\u30f4"
            return chr(ord(c) + offset)

        def fix_voicing(self) -> None:
            self._formatted = re.sub(
                r".[\u309b\u3099]",
                lambda mo: self._replace(mo.group(0), 1),
                self._formatted,
            )

        def fix_half_voicing(self) -> None:
            self._formatted = re.sub(
                r".[\u309a\u309c]",
                lambda mo: self._replace(mo.group(0), 2),
                self._formatted,
            )

        @property
        def formatted(self) -> str:
            return self._formatted

    def rename_pseudo_voicing() -> None:
        pane = CPane()
        renamer = Renamer()
        items = pane.selectedItems
        for item in items:
            if not renamer.renamable(item):
                continue
            name = item.getName()
            pv = PseudoVoicing(name)
            pv.fix_voicing()
            pv.fix_half_voicing()
            new_name = pv.formatted
            org_path = Path(item.getFullpath())
            renamer.execute(org_path, new_name)

    def save_clipboard_image_as_file() -> None:
        pane = CPane()

        def _save(job_item: ckit.JobItem) -> None:
            job_item.file_name = ""
            img = ImageGrab.grabclipboard()
            if not img or isinstance(img, list):
                kiritori.log("Canceled: No image in clipboard.")
                return
            job_item.file_name = (
                datetime.datetime.today().strftime("%Y%m%d-%H%M%S") + ".png"
            )
            save_path = os.path.join(pane.currentPath, job_item.file_name)
            img.save(save_path)

        def _finish(job_item: ckit.JobItem) -> None:
            if job_item.file_name:
                pane.refresh()
                pane.focusByName(job_item.file_name)

        job = ckit.JobItem(_save, _finish)
        window.taskEnqueue(job, create_new_queue=False)

    keybinder.bind(save_clipboard_image_as_file, "C-S-I")

    class PathMatchFilter:
        def __init__(self, root: str, names: list[str]) -> None:
            self.root = root
            self.names = names

        def __call__(self, item) -> bool:
            path = item.getFullpath()
            if path.startswith(self.root) and len(self.root) < len(path):
                for name in self.names:
                    p = os.path.join(self.root, name)
                    if path.startswith(p):
                        return True
                return False
            return True

        def __str__(self) -> str:
            return f"\U0001f50d[{Path(self.root).name}]"

    def hide_unselected() -> None:
        pane = CPane()
        if pane.hasSelection:
            names = pane.selectedItemNames
            window.subThreadCall(
                pane.fileList.setFilter, (PathMatchFilter(pane.currentPath, names),)
            )
            pane.refresh()
            pane.focus(0)
            pane.repaint(PaintOption.Focused)
            CPane().unSelectAll()

    keybinder.bind(hide_unselected, "S-H")

    def clear_filter() -> None:
        pane = CPane()
        window.subThreadCall(pane.fileList.setFilter, (filter_Default("*"),))
        pane.refresh()
        pane.repaint(PaintOption.Focused)

    keybinder.bind(clear_filter, "Q")

    def make_junction() -> None:
        active_pane = CPane()
        if not active_pane.hasSelection:
            return

        other_pane = CPane(False)
        dest = other_pane.currentPath
        for src_path in active_pane.selectedItemPaths:
            junction_path = Path(dest, Path(src_path).name)
            if smart_check_path(junction_path):
                kiritori.log(f"'{junction_path}' already exists.")
                return
            try:
                cmd = ["cmd", "/c", "mklink", "/J", str(junction_path), src_path]
                proc = subprocess.run(cmd, capture_output=True, encoding="cp932")
                result = proc.stdout.strip()
                kiritori.log(result)
            except Exception as e:
                kiritori.log(e)
                return

    def reset_hotkey() -> None:
        window.ini.set("HOTKEY", "activate_vk", "0")
        window.ini.set("HOTKEY", "activate_mod", "0")

    def update_command_list(command_table: dict) -> None:
        for name, func in command_table.items():
            window.launcher.command_list += [(name, keybinder.wrap(func))]

    update_command_list(
        {
            "GitInit": git_init,
            "ChangeImageType": change_image_type,
            "MakeShortcut": make_shortcut,
            "CleanTempFiles": remove_tempfiles,
            "RenamePhotoFileByExifDate": rename_photo_file_by_exifdate,
            "RenameLightroomPhoto": rename_lightroom_photo_from_dropbox,
            "ZipSelections": compress_files,
            "SetBookmarkAlias": set_bookmark_alias,
            "BookmarkHere": bookmark_here,
            "DocxToTxt": docx_to_txt,
            "EjectCurrentDrive": eject_current_drive,
            "ConcPdfGo": concatenate_pdf,
            "MakeJunction": make_junction,
            "ResetHotkey": reset_hotkey,
            "UnzipSelections": extract_archives,
            "HideUnselectedItems": hide_unselected,
            "ClearFilter": clear_filter,
            "CopyDirTree": copy_dir_tree,
            "Diffinity": lambda: diff_files(with_diffinity=True),
            "DiffWithVSCode": lambda: diff_files(with_diffinity=False),
            "MultipleSelectedItem": multiple_selected_item,
            "MakeInternetShortcut": lambda: make_internet_shortcut(
                ckit.getClipboardText().strip()
            ),
            "RenamePseudoVoicing": rename_pseudo_voicing,
            "RenameIndex": rename_index,
            "RenameInsert": rename_insert,
            "RenameExtension": rename_ext,
            "RenameRegExp": rename_regexp,
            "RenameStem": rename_stem,
            "RenameSubstr": rename_substr,
            "FindSameFile": FileHashDiff(2).compare,
            "FromOtherNames": from_other_names,
            "FromActiveNames": from_active_names,
            "SelectSameName": select_same_name,
            "SelectNameUnique": select_name_unique,
            "SelectNameCommon": select_name_common,
            "SelectStemMatchCase": invoke_regex_selector(True),
            "SelectStemMatch": invoke_regex_selector(False),
            "SelectStemStartsWith": select_stem_startswith,
            "SelectStemEndsWith": select_stem_endswith,
            "SelectStemContains": select_stem_contains,
            "SelectByExtension": select_byext,
        }
    )
