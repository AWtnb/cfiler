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
from typing import Callable, Iterator

import cfiler_msgbox  # type: ignore
import ckit  # type: ignore
import pyauto  # type: ignore
from cfiler import *  # type: ignore
from cfiler_filelist import filter_Default  # type: ignore
from PIL import ImageGrab  # type: ignore

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
    snapper,
)
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
from .tools.office import docx_to_txt, read_openxml
from .tools.protocols import ItemDefaultProtocol
from .tools.rename import affix_handler, renamer
from .tools.rename import extension as rename_ext
from .tools.rename import index as rename_index
from .tools.rename import ini as rename_ini
from .tools.rename import insert as rename_insert
from .tools.rename import photo as rename_photo
from .tools.rename import regexp as rename_regexp
from .tools.rename import stem as rename_stem
from .tools.rename import substr as rename_substr


def setup(window) -> None:

    affix_handler.setup(window)
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
    rename_ext.setup(window)
    rename_index.setup(window)
    rename_ini.setup(window)
    rename_insert.setup(window)
    rename_photo.setup(window)
    rename_regexp.setup(window)
    rename_stem.setup(window)
    rename_substr.setup(window)
    renamer.setup(window)
    selector.setup(window)
    snapper.setup(window)
    style.setup(window)

    window.enter_hook = enter.hook_enter

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

    keybinder.bind(bookmark.toggle_bookmark, "C-B")
    keybinder.bind(lambda: bookmark.fuzzy_bookmark(False), "B")
    keybinder.bind(lambda: bookmark.fuzzy_bookmark(True), "A-S-B")

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

    keybinder.bind(cursor_mover.smart_cursorUp, "K", "Up")
    keybinder.bind(cursor_mover.smart_cursorDown, "J", "Down")
    keybinder.bind(cursor_mover.focus_latest_item, "A-N")

    def select_empty_dir() -> None:
        pane = cpane.CPane()
        for d in pane.dirs:
            path = Path(d.getFullpath())
            if not any(path.iterdir()):
                pane.selectByName(path.name)

    keybinder.bind(select_empty_dir, "A-E")

    def copy_dir_tree() -> None:
        pane = cpane.CPane()
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

    keybinder.bind(change_dir.open_latest_under_tree, "S-A-N")
    keybinder.bind(cursor_mover.focus_by_timestamp, "A-Back", "A-B")

    def git_init() -> None:
        pane = cpane.CPane()
        path = pane.currentPath
        git_path = os.path.join(path, ".git")
        if smart_check_path(git_path):
            kiritori.log(f"'{git_path}' already exists.")
            return
        shell_exec("git", "init", str(path))

    def open_lazygit() -> None:
        pane = cpane.CPane()
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

    keybinder.bind(cpane.adjust_pane_width, "C-S")

    keybinder.bind(lambda: cpane.CPane().focusOther(), "C-L")

    keybinder.bind(window.command_Enter, "L", "Right")

    def toggle_hidden() -> None:
        window.showHiddenFile(not window.isHiddenFileVisible())

    keybinder.bind(toggle_hidden, "C-S-H")

    keybinder.bind(enter.open_with, "C-O")

    def open_with_smooth_csv(_) -> None:
        smooth_csv_path = r"C:\Program Files\SmoothCSV\smoothcsv-app.exe"
        if not smart_check_path(smooth_csv_path):
            return

        pane = cpane.CPane()
        target = pane.selectedItemPaths
        if len(target) < 1:
            target = [pane.focusedItemPath]

        for p in target:
            if Path(p).suffix in [".csv", ".txt"]:
                shell_exec(smooth_csv_path, p)

    keybinder.bind(open_with_smooth_csv, "Comma")

    def quick_move() -> None:
        pane = cpane.CPane()
        if not pane.hasSelection:
            window.command_Select(None)
        pane.adjustWidth()
        window.command_Move(None)

    keybinder.bind(quick_move, "M")

    def quick_copy() -> None:
        pane = cpane.CPane()
        if not pane.hasSelection:
            window.command_Select(None)
        pane.adjustWidth()
        window.command_Copy(None)

    keybinder.bind(quick_copy, "C")

    keybinder.bind(cpane.swap_pane, "S")

    ckit.CronTable.defaultCronTable().add(clon.invoke_tempfile_cleaner())

    keybinder.bind(change_dir.zyw.invoke(skip_file=True), "Z")
    keybinder.bind(change_dir.zyw.invoke(skip_file=False), "S-Z")
    keybinder.bind(cursor_mover.fuzzy_focus, "S-F")

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

        pane = cpane.CPane()
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

        pane = cpane.CPane()
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
            Path(cpane.CPane().currentPath, name).write_text(
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
        cpane.CPane().openPath(c.strip().strip('"'))

    keybinder.bind(on_paste, "C-V", "S-Insert")
    keybinder.bind(change_dir.change_drive, "D")
    keybinder.bind(change_dir.go_to, "C-G")

    keybinder.bind(change_dir.to_ghq_repo, "G")

    def eject_current_drive() -> None:
        pane = cpane.CPane()
        current = pane.currentPath
        if current.startswith("C:"):
            return

        current_drive = Path(current).drive
        other = cpane.CPane(False)
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
        pane = cpane.CPane()
        p = pane.currentPath
        ckit.setClipboardText(p)
        window.setStatusMessage(f"copied current path: '{p}'", 3000)

    keybinder.bind(copy_current_path, "C-A-P")

    def on_copy() -> None:
        selection_left, selection_right = window.log_pane.selection
        if selection_left != selection_right:
            window.command_SetClipboard_LogSelected(None)
            return

        pane = cpane.CPane()

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

        result, _ = listwindow.invoke("Copy", menu)
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
        cpane.CPane().unSelectAll()
        cpane.CPane(False).unSelectAll()

    keybinder.bind(unselect_panes, "C-U", "S-Esc")

    def smart_jumpDown(by_prefix: bool, selecting: bool) -> CallbackFunc:
        def _jumper() -> None:
            cursor_jumper.CursorJumper(by_prefix).down(selecting)

        return _jumper

    keybinder.bind(smart_jumpDown(True, False), "A-J")
    keybinder.bind(smart_jumpDown(True, True), "S-A-J")
    keybinder.bind(smart_jumpDown(False, False), "C-J")
    keybinder.bind(smart_jumpDown(False, True), "S-C-J")

    def smart_jumpUp(by_prefix: bool, selecting: bool) -> CallbackFunc:
        def _jumper() -> None:
            cursor_jumper.CursorJumper(by_prefix).up(selecting)

        return _jumper

    keybinder.bind(smart_jumpUp(True, False), "A-K")
    keybinder.bind(smart_jumpUp(True, True), "S-A-K")
    keybinder.bind(smart_jumpUp(False, False), "C-K")
    keybinder.bind(smart_jumpUp(False, True), "S-C-K")

    def duplicate_pane() -> None:
        window.command_ChdirInactivePaneToOther(None)
        pane = cpane.CPane()
        pane.focusOther()

    keybinder.bind(duplicate_pane, "W")

    def open_on_explorer() -> None:
        pane = cpane.CPane(True)
        shell_exec(pane.currentPath)

    keybinder.bind(open_on_explorer, "C-S-E")

    def open_to_other() -> None:
        pane = cpane.CPane(True)
        if not pane.isBlank:
            cpane.CPane(False).openPath(pane.focusedItemPath)
            pane.focusOther()

    keybinder.bind(open_to_other, "S-L")

    def open_parent_to_other() -> None:
        pane = cpane.CPane(True)
        parent, current_name = os.path.split(pane.currentPath)
        cpane.CPane(False).openPath(parent, current_name)
        pane.focusOther()

    keybinder.bind(open_parent_to_other, "S-U")

    def on_vscode() -> None:
        pane = cpane.CPane()
        open_vscode(pane.currentPath)

    keybinder.bind(on_vscode, "V")

    keybinder.bind(rename_substr.execute, "S-S")

    keybinder.bind(rename_insert.execute, "S-I")

    keybinder.bind(rename_index.execute, "A-S-I")

    keybinder.bind(rename_regexp.execute, "S-R")

    def invoke_name_candidate_handler() -> Callable[
        [ckit.ckit_widget.EditWidget.UpdateInfo], tuple[list[str], int]
    ]:
        pane = cpane.CPane()
        prefix_candidates = affix_handler.get_prefix_candidates(pane)
        suffix_candidates = affix_handler.get_suffix_candidates(pane)
        selected = affix_handler.get_selected_stems(
            pane
        ) + affix_handler.get_selected_stems(cpane.CPane(False))

        def _filter(user_input: str) -> list[str]:
            if affix_handler.SEP not in user_input:
                return affix_handler.filter_prefixes(prefix_candidates, user_input)
            return affix_handler.filter_suffixes(suffix_candidates, user_input)

        def _handler(
            update_info: ckit.ckit_widget.EditWidget.UpdateInfo,
        ) -> tuple[list[str], int]:
            affix = _filter(update_info.text)
            return selected + affix, 0

        return _handler

    keybinder.bind(rename_stem.execute, "N")

    keybinder.bind(rename_ext.execute, "S-N")

    def multiple_selected_item() -> None:
        pane = cpane.CPane()
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
        pane = cpane.CPane()

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
                candidate_handler=affix_handler.invoke_suffix_handler(),
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
        pane = cpane.CPane()

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

        pane = cpane.CPane()

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
        pane = cpane.CPane()
        ts = datetime.datetime.today().strftime("%Y%m%d")
        result, mod = window.commandLine(
            "DirName",
            text=ts,
            selection=[0, len(ts)],
            candidate_handler=invoke_name_candidate_handler(),
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
        pane = cpane.CPane()
        if not hasattr(pane.fileList.getLister(), "touch"):
            return

        result, mod = window.commandLine(
            "Stem",
            candidate_handler=invoke_name_candidate_handler(),
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

    keybinder.bind(snapper.to_home_position, "C-0")

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
        cpane.LeftPane().setSorter(sorter)
        cpane.RightPane().setSorter(sorter)

    setup_sorter()

    def reload_config() -> None:
        window.configure()
        ts = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S.%f")
        window.setStatusMessage(f"Reloaded config.py | {ts}", 2000)

    keybinder.bind(reload_config, "C-R", "F5")

    def open_desktop_to_other() -> None:
        pane = cpane.CPane()
        other = cpane.CPane(False)
        if DESKTOP_PATH not in [pane.currentPath, other.currentPath]:
            other.openPath(DESKTOP_PATH)
        pane.focusOther()

    keybinder.bind(open_desktop_to_other, "A-O")

    def starting_position(both_pane: bool = False) -> None:
        window.command_MoveSeparatorCenter(None)
        pane = cpane.CPane()
        if pane.currentPath != DESKTOP_PATH:
            pane.openPath(DESKTOP_PATH)
        if both_pane:
            window.command_ChdirInactivePaneToOther(None)
            cpane.LeftPane().activate()

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

        left = cpane.LeftPane()
        right = cpane.RightPane()
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
        pane = cpane.CPane()
        target = pane.selectedItemNames
        if len(target) < 1:
            target.append(pane.focusedItem.getName())

        other_pane_dir = cpane.CPane(False).currentPath
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
            pane = cpane.CPane()
            other_pane = cpane.CPane(False)
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
        pane = cpane.CPane()
        left_path = ""
        right_path = ""

        if (
            pane.hasSelection
            and len(pane.selectedItems) == 2
            and not cpane.CPane(False).hasSelection
        ):
            left_path, right_path = pane.selectedItemPaths
        else:
            left_pane = cpane.LeftPane()
            right_pane = cpane.RightPane()
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
        pane = cpane.CPane()
        pane.unSelectAll()
        active_names = pane.names
        other = cpane.CPane(False)
        other_names = [item.getName() for item in other.selectedOrAllItems]
        for name in active_names:
            if name in other_names:
                pane.selectByName(name)

    def from_active_names() -> None:
        pane = cpane.CPane()
        active_names = [item.getName() for item in pane.selectedOrAllItems]
        other = cpane.CPane(False)
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
        pane = cpane.CPane()
        active_names = pane.selectedItemNames
        if len(active_names) < 1:
            active_names = [pane.focusedItem.getName()]
        other = cpane.CPane(False)
        other.unSelectAll()

        for name in other.names:
            if name in active_names:
                other.selectByName(name)

    def select_name_common() -> None:
        pane = cpane.CPane()
        pane.unSelectAll()
        active_names = pane.names
        other = cpane.CPane(False)
        other.unSelectAll()
        other_names = other.names

        for name in active_names:
            if name in other_names:
                pane.selectByName(name)
        for name in other_names:
            if name in active_names:
                other.selectByName(name)

    def select_name_unique() -> None:
        pane = cpane.CPane()
        pane.unSelectAll()
        active_names = pane.names
        other = cpane.CPane(False)
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
            candidate_handler=affix_handler.invoke_prefix_handler(),
        )
        if result:
            selector.stem_starts_with(result, mod == ckit.MODKEY_SHIFT)

    keybinder.bind(select_stem_startswith, "Caret")

    def select_stem_endswith() -> None:
        result, mod = window.commandLine(
            "EndsWith",
            return_modkey=True,
            candidate_handler=affix_handler.invoke_suffix_handler(),
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
        pane = cpane.CPane()
        exts = []
        for item in pane.selectedOrAllItems:
            ext = Path(item.getFullpath()).suffix[1:]
            if ext and ext not in exts:
                exts.append(ext)

        if len(exts) < 1:
            return

        result, mod = listwindow.invoke("Select Extension", exts)

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
        pane = cpane.CPane()
        items = pane.selectedItems
        for item in items:
            if not renamer.is_renamable(item):
                continue
            name = item.getName()
            pv = PseudoVoicing(name)
            pv.fix_voicing()
            pv.fix_half_voicing()
            new_name = pv.formatted
            org_path = Path(item.getFullpath())
            renamer.execute(pane, org_path, new_name)

    def save_clipboard_image_as_file() -> None:
        pane = cpane.CPane()

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
        pane = cpane.CPane()
        if pane.hasSelection:
            names = pane.selectedItemNames
            window.subThreadCall(
                pane.fileList.setFilter, (PathMatchFilter(pane.currentPath, names),)
            )
            pane.refresh()
            pane.focus(0)
            pane.repaint(PaintOption.Focused)
            cpane.CPane().unSelectAll()

    keybinder.bind(hide_unselected, "S-H")

    def clear_filter() -> None:
        pane = cpane.CPane()
        window.subThreadCall(pane.fileList.setFilter, (filter_Default("*"),))
        pane.refresh()
        pane.repaint(PaintOption.Focused)

    keybinder.bind(clear_filter, "Q")

    def make_junction() -> None:
        active_pane = cpane.CPane()
        if not active_pane.hasSelection:
            return

        other_pane = cpane.CPane(False)
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
            "CleanTempFiles": clon.remove_tempfiles,
            "RenamePhotoFileByExifDate": rename_photo.execute_with_exif,
            "RenameLightroomPhoto": rename_photo.execute_for_lightroom_photo_from_dropbox,
            "ZipSelections": archiver.compress,
            "SetBookmarkAlias": bookmark.set_bookmark_alias,
            "BookmarkHere": bookmark.bookmark_here,
            "DocxToTxt": docx_to_txt,
            "EjectCurrentDrive": eject_current_drive,
            "ConcPdfGo": concatenate_pdf,
            "MakeJunction": make_junction,
            "ResetHotkey": reset_hotkey,
            "UnzipSelections": archiver.extract,
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
            "RenameIndex": rename_index.execute,
            "RenameInsert": rename_insert.execute,
            "RenameExtension": rename_ext.execute,
            "RenameRegExp": rename_regexp.execute,
            "RenameStem": rename_stem.execute,
            "RenameSubstr": rename_substr.execute,
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
