import sys
import datetime
import os
import re
import shutil
import hashlib
import subprocess

from pathlib import Path
from typing import Callable

import ckit
import pyauto

from cfiler import *

# https://github.com/crftwr/cfiler/blob/master/cfiler_mainwindow.py
from cfiler_mainwindow import MainWindow

# https://github.com/crftwr/cfiler/blob/master/cfiler_filelist.py
from cfiler_filelist import FileList, item_Base, lister_Default

from cfiler_listwindow import popMenu

USER_PROFILE = os.environ.get("USERPROFILE") or ""
LINE_BREAK = os.linesep


def configure(window: MainWindow):

    window.maximize()

    window.keymap["C-Comma"] = window.command_ConfigMenu
    window.keymap["C-S-Comma"] = window.command_ConfigMenu2
    window.keymap["A-J"] = window.command_JumpList
    window.keymap["C-L"] = window.command_Execute

    window.keymap["A-C-H"] = window.command_JumpHistory
    window.keymap["C-D"] = window.command_Delete
    window.keymap["P"] = window.command_FocusOther
    window.keymap["C-L"] = window.command_FocusOther
    window.keymap["S-O"] = window.command.ChdirActivePaneToOther
    window.keymap["O"] = window.command.ChdirInactivePaneToOther

    window.keymap["A"] = window.command_CursorTop
    window.keymap["E"] = window.command_CursorBottom
    window.keymap["Home"] = window.command_CursorTop
    window.keymap["End"] = window.command_CursorBottom
    window.keymap["J"] = window.command_CursorDown
    window.keymap["K"] = window.command_CursorUp
    window.keymap["C-J"] = window.command_CursorDownSelected
    window.keymap["C-K"] = window.command_CursorUpSelected
    window.keymap["C-Down"] = window.command_CursorDownSelected
    window.keymap["C-Up"] = window.command_CursorUpSelected

    def update_jump_list(jump_table: dict) -> None:
        for name, path in jump_table.items():
            p = Path(path)
            if p.exists() and p.is_dir():
                window.jump_list += [(name, str(p))]

    update_jump_list(
        {
            "Desktop": str(Path(USER_PROFILE, "Desktop")),
            "Scan": r"X:\scan",
            "Dropbox Share": str(
                Path(USER_PROFILE, "Dropbox", "_sharing", "_yuhikaku")
            ),
        }
    )

    class CPane:
        def __init__(self, window: MainWindow, active: bool = True) -> None:
            self._window = window
            if active:
                self._pane = self._window.activePane()
            else:
                self._pane = self._window.inactivePane()

        def refresh(self) -> None:
            self._window.paint()

        @property
        def cursor(self) -> int:
            return self._pane.cursor

        def focus(self, i: int) -> None:
            self._pane.cursor = i

        @property
        def file_list(self) -> FileList:
            return self._pane.file_list

        @property
        def scroll_info(self) -> ckit.ScrollInfo:
            return self._pane.scroll_info

        @property
        def current_path(self) -> str:
            return self.file_list.getLocation()

        @property
        def count(self) -> int:
            return self.file_list.numItems()

        def byIndex(self, i: int) -> item_Base:
            return self.file_list.getItem(i)

        @property
        def names(self) -> list:
            names = []
            for i in range(self.count):
                item = self.byIndex(i)
                names.append(item.getName())
            return names

        @property
        def selectedItems(self) -> list:
            items = []
            for i in range(self.count):
                item = self.byIndex(i)
                if item.selected():
                    items.append(item)
            return items

        @property
        def selectedItemPaths(self) -> list:
            paths = []
            for i in range(self.count):
                item = self.byIndex(i)
                if item.selected():
                    path = self.pathByIndex(i)
                    paths.append(path)
            return paths

        @property
        def focusItem(self) -> item_Base:
            return self.byIndex(self.cursor)

        def pathByIndex(self, i: int) -> str:
            item = self.byIndex(i)
            return str(Path(self.current_path, item.getName()))

        @property
        def focusItemPath(self) -> str:
            return self.pathByIndex(self.cursor)

        def toggleSelect(self, i: int) -> None:
            self.file_list.selectItem(i, None)

        def select(self, i: int) -> None:
            self.file_list.selectItem(i, True)

        def unSelect(self, i: int) -> None:
            self.file_list.selectItem(i, False)

        @property
        def selectionTop(self) -> int:
            for i in range(self.count):
                if self.byIndex(i).selected():
                    return i
            return -1

        @property
        def selectionBottom(self) -> int:
            idxs = []
            for i in range(self.count):
                if self.byIndex(i).selected():
                    idxs.append(i)
            if len(idxs) < 1:
                return -1
            return idxs[-1]

        def openPath(self, path: str) -> bool:
            # https://github.com/crftwr/cfiler/blob/0d1017e93939b53024b9ba80492c428d3ae24b8b/cfiler_mainwindow.py#L3117
            if not Path(path).exists() or Path(path).is_file():
                print("invalid dir path: {}".format(path))
                return False
            lister = lister_Default(self._window, path)
            self._window.jumpLister(self._pane, lister)
            return True

    class LeftPane(CPane):
        def __init__(self, window: MainWindow) -> None:
            super().__init__(window, (window.focus == MainWindow.FOCUS_LEFT))

    class RightPane(CPane):
        def __init__(self, window: MainWindow) -> None:
            super().__init__(window, (window.focus == MainWindow.FOCUS_RIGHT))

    def keybind(func: Callable):
        def _callback(info):
            func()

        return _callback

    def zyl():
        exe_path = Path(USER_PROFILE, r"Personal\tools\bin\zyl.exe")
        src_path = Path(USER_PROFILE, r"Personal\launch.yaml")
        if exe_path.exists() and src_path.exists():
            cmd = [
                str(exe_path),
                "-src={}".format(src_path),
                "-all=False",
                "-exclude=_obsolete,node_modules",
                "-stdout=True",
            ]
            proc = subprocess.run(cmd, stdout=subprocess.PIPE)
            if proc.returncode != 0:
                return
            result = proc.stdout.decode("utf-8").strip()
            pane = CPane(window)
            pane.openPath(result)

    window.keymap["C-S-Z"] = keybind(zyl)

    class zyc:
        def __init__(self, search_all: bool) -> None:
            self._exe_path = Path(USER_PROFILE, r"Personal\tools\bin\zyc.exe")
            self._cmd = [
                str(self._exe_path),
                "-exclude=_obsolete,node_modules",
                "-stdout=True",
                "-all={}".format(search_all),
            ]

        def check(self) -> bool:
            return self._exe_path.exists()

        def for_dir(self, offset: int) -> Callable:
            def _func() -> None:
                if not self.check():
                    return
                pane = CPane(window)
                cmd = self._cmd + [
                    "-offset={}".format(offset),
                    "-cur={}".format(pane.current_path),
                ]
                proc = subprocess.run(cmd, stdout=subprocess.PIPE)
                if proc.returncode != 0:
                    return
                result = proc.stdout.decode("utf-8").strip()
                if Path(result).is_dir():
                    pane = CPane(window)
                    pane.openPath(result)
                else:
                    pyauto.shellExecute(None, result, "", "")

            return _func

    window.keymap["Z"] = keybind(zyc(False).for_dir(-1))
    window.keymap["A-Z"] = keybind(zyc(True).for_dir(-1))
    window.keymap["S-Z"] = keybind(zyc(False).for_dir(1))
    window.keymap["A-S-Z"] = keybind(zyc(True).for_dir(1))
    window.keymap["C-F"] = keybind(zyc(True).for_dir(0))

    def to_top_selection():
        pane = CPane(window)
        i = pane.selectionTop
        if -1 < i:
            pane.focus(i)
            pane.scroll_info.makeVisible(i, window.fileListItemPaneHeight(), 1)
            pane.refresh()

    window.keymap["C-A-K"] = keybind(to_top_selection)

    def to_bottom_selection():
        pane = CPane(window)
        i = pane.selectionBottom
        if -1 < i:
            pane.focus(i)
            pane.scroll_info.makeVisible(i, window.fileListItemPaneHeight(), 1)
            pane.refresh()

    window.keymap["C-A-J"] = keybind(to_bottom_selection)

    def smart_copy_path():
        pane = CPane(window)
        paths = []
        for i in range(pane.count):
            item = pane.byIndex(i)
            if item.selected():
                paths.append(pane.pathByIndex(i))

        if len(paths) < 1:
            path = pane.focusItemPath
            paths.append(path)

        lines = LINE_BREAK.join(paths)
        ckit.setClipboardText(lines)
        print("copied:\n{}\n".format(lines))

    window.keymap["C-A-P"] = keybind(smart_copy_path)

    def smart_enter():
        pane = CPane(window)
        if pane.focusItem.isdir():
            window.command_Enter(None)
        else:
            window.command_Execute(None)

    window.keymap["L"] = keybind(smart_enter)
    window.keymap["H"] = window.command_GotoParentDir

    class Selector:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

        @property
        def pane(self) -> CPane:
            return CPane(self._window)

        def allItems(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                pane.select(i)
            pane.refresh()

        def allFiles(self) -> None:
            self.clearAll()
            pane = self.pane
            for i in range(pane.count):
                if not pane.byIndex(i).isdir():
                    pane.select(i)
            pane.refresh()

        def allDirs(self) -> None:
            self.clearAll()
            pane = self.pane
            for i in range(pane.count):
                if pane.byIndex(i).isdir():
                    pane.select(i)
            pane.refresh()

        def clearAll(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                pane.unSelect(i)
            pane.refresh()

        def toTop(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if i <= pane.cursor:
                    pane.select(i)
            pane.refresh()

        def toEnd(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if pane.cursor <= i:
                    pane.select(i)
            pane.refresh()

    SELECTOR = Selector(window)

    window.keymap["C-A"] = keybind(SELECTOR.allItems)
    window.keymap["C-U"] = keybind(SELECTOR.clearAll)
    window.keymap["F"] = keybind(SELECTOR.allFiles)
    window.keymap["D"] = keybind(SELECTOR.allDirs)
    window.keymap["S-Home"] = keybind(SELECTOR.toTop)
    window.keymap["S-A"] = keybind(SELECTOR.toTop)
    window.keymap["S-End"] = keybind(SELECTOR.toEnd)
    window.keymap["S-E"] = keybind(SELECTOR.toEnd)

    def open_to_other():
        active_pane = CPane(window, True)
        inactive_pane = CPane(window, False)
        inactive_pane.openPath(active_pane.focusItemPath)
        window.command_FocusOther(None)

    window.keymap["S-L"] = keybind(open_to_other)

    def open_parent_to_other():
        active_pane = CPane(window, True)
        parent = str(Path(active_pane.current_path).parent)
        inactive_pane = CPane(window, False)
        inactive_pane.openPath(parent)
        window.command_FocusOther(None)

    window.keymap["U"] = keybind(open_parent_to_other)

    def on_vscode():
        vscode_path = Path(USER_PROFILE, r"scoop\apps\vscode\current\Code.exe")
        if vscode_path.exists():
            pane = CPane(window)
            pyauto.shellExecute(None, str(vscode_path), pane.current_path, "")

    window.keymap["A-V"] = keybind(on_vscode)

    def duplicate_with_name():
        pane = CPane(window)
        focus_path = Path(pane.focusItemPath)
        if focus_path.is_dir():
            print("directory copy is dangerous!")
            return
        result = window.commandLine(
            "NewFileName",
            text=focus_path.name,
            selection=[0, len(focus_path.stem)],
        )

        if result and result != pane.focusItem.getName():
            result = result.strip()
            if len(result) < 1:
                return
            new_path = focus_path.with_name(result)
            if new_path.exists():
                print("same file exists!")
                return
            try:
                shutil.copy(str(focus_path), new_path)
            except Exception as e:
                print(e)

    window.keymap["S-D"] = keybind(duplicate_with_name)

    window.keymap["A-C"] = window.command_ContextMenu
    window.keymap["A-S-C"] = window.command_ContextMenuDir

    def new_txt():
        pane = CPane(window)
        if not hasattr(pane.file_list.getLister(), "touch"):
            return
        result = window.commandLine("NewTextFileName")
        if not result:
            return
        filename = result.strip()
        if len(filename) < 1:
            return
        if not filename.endswith(".txt"):
            filename = filename + ".txt"
        if Path(pane.current_path, filename).exists():
            return
        window.subThreadCall(pane.file_list.getLister().touch, (filename,))
        window.subThreadCall(pane.file_list.refresh, ())
        pane.file_list.applyItems()
        pane.focus(window.cursorFromName(pane.file_list, filename))
        pane.scroll_info.makeVisible(pane.cursor, window.fileListItemPaneHeight(), 1)
        pane.refresh()

    window.keymap["T"] = keybind(new_txt)

    def to_obsolete_dir():
        pane = CPane(window)
        if not hasattr(pane.file_list.getLister(), "mkdir"):
            return

        items = []
        for i in range(pane.count):
            item = pane.byIndex(i)
            if item.selected() and hasattr(item, "delete"):
                items.append(item)
        if len(items) < 1:
            return

        dest_name = "_obsolete"
        if not Path(pane.current_path, dest_name).exists():
            window.subThreadCall(
                pane.file_list.getLister().mkdir, (dest_name, sys.stdout.write)
            )

        child_lister = pane.file_list.getLister().getChild(dest_name)
        window._copyMoveCommon(
            pane,
            pane.file_list.getLister(),
            child_lister,
            items,
            "m",
            pane.file_list.getFilter(),
        )
        child_lister.destroy()

    window.keymap["A-O"] = keybind(to_obsolete_dir)

    def reload_config():
        window.configure()
        window.command_MoveSeparatorCenter(None)
        ts = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
        print("{} reloaded config.py\n".format(ts))

    window.keymap["C-R"] = keybind(reload_config)
    window.keymap["F5"] = keybind(reload_config)

    def open_doc():
        help_path = str(Path(ckit.getAppExePath(), "doc", "index.html"))
        pyauto.shellExecute(None, help_path, "", "")

    window.keymap["A-H"] = keybind(open_doc)

    def edit_config():
        dir_path = Path(USER_PROFILE, r"Sync\develop\repo\cfiler")
        if dir_path.exists():
            dp = str(dir_path)
            vscode_path = Path(USER_PROFILE, r"scoop\apps\vscode\current\Code.exe")
            if vscode_path.exists():
                vp = str(vscode_path)
                pyauto.shellExecute(None, vp, dp, "")
            else:
                pyauto.shellExecute(None, dp, "", "")
        else:
            pyauto.shellExecute(None, USER_PROFILE, "", "")
            print("cannot find repo dir. open user profile instead.")

    window.keymap["C-E"] = keybind(edit_config)

    window.keymap["C-S-N"] = window.command_Mkdir

    def template_mkdir():
        dir_names = [
            ("_legacy",),
            ("_wiki",),
            ("appendix_付き物",),
            ("author_著者紹介",),
            ("design_装幀",),
            ("document_依頼書類",),
            ("document_入稿書類",),
            ("donation_献本",),
            ("endroll_奥付",),
            ("galley_ゲラ",),
            ("index_索引",),
            ("layout_割付",),
            ("letter_手紙",),
            ("marginalia",),
            ("meeting_会合",),
            ("permission_許諾",),
            ("plain",),
            ("postscript_あとがき",),
            ("postscript_おわりに",),
            ("preface_はじめに",),
            ("preface_まえがき",),
            ("preprocess_データ整形",),
            ("projectpaper_企画書",),
            ("promote_販宣",),
            ("proofed_by_author",),
            ("proofed",),
            ("reference_文献リスト",),
            ("send_to_author",),
            ("send_to_printshop",),
            ("toc_目次",),
            ("websupport",),
            ("written_お原稿",),
            ("jizen", "事前資料"),
            ("kaigo", "会合メモ"),
            ("shoko", "初校"),
            ("saiko", "再校"),
            ("sanko", "三校"),
            ("nenko", "念校"),
            ("gijiroku", "議事録"),
        ]

        pane = CPane(window)
        if not hasattr(pane.file_list.getLister(), "mkdir"):
            return

        options = []
        for dn in dir_names:
            if len(dn) == 2:
                s = "{}[{}]".format(*dn)
                options.append((s, dn[1]))
            else:
                options.append((dn[0], dn[0]))
        result = popMenu(window, "DirNames", options, 0)
        if result < 0:
            return
        name = options[result][0]

        indexes = []
        reg = re.compile(r"^\d+(?=_)")
        for i in range(pane.count):
            item = pane.byIndex(i)
            if Path(pane.pathByIndex(i)).is_dir():
                n = item.getName()
                if m := reg.match(n):
                    indexes.append(m[0])
        pref = ""
        if 0 < len(indexes):
            l = indexes[-1]
            pref = "0" * (len(l) - 1) + "{}_".format(int(l) + 1)
        name = pref + name
        window.subThreadCall(pane.file_list.getLister().mkdir, (name, sys.stdout.write))

        window.subThreadCall(pane.file_list.refresh, ())
        pane.file_list.applyItems()
        pane.focus(window.cursorFromName(pane.file_list, name))
        pane.scroll_info.makeVisible(pane.cursor, window.fileListItemPaneHeight(), 1)
        pane.refresh()

    window.keymap["A-S-N"] = keybind(template_mkdir)

    ################################
    ################################
    ################################
    ################################
    ################################

    # https://github.com/crftwr/cfiler/blob/0d1017e93939b53024b9ba80492c428d3ae24b8b/_config.py#L284
    def command_CheckEmpty(_):

        pane = window.activePane()
        location = window.activeFileList().getLocation()
        items = window.activeItems()

        result_items = []
        message = [""]

        def jobCheckEmpty(job_item):

            def printBoth(s):
                print(s)
                message[0] += s + "\n"

            def appendResult(item):
                result_items.append(item)
                printBoth("   %s" % item.getName())

            printBoth("空のディレクトリを検索 :")

            # ビジーインジケータ On
            window.setProgressValue(None)

            for item in items:

                if not item.isdir():
                    continue

                if job_item.isCanceled():
                    break
                if job_item.waitPaused():
                    window.setProgressValue(None)

                empty = True

                for root, dirs, files in item.walk(False):

                    if job_item.isCanceled():
                        break
                    if job_item.waitPaused():
                        window.setProgressValue(None)

                    if not empty:
                        break
                    for file in files:
                        empty = False
                        break

                if empty:
                    appendResult(item)

            message[0] += "\n"
            message[0] += "検索結果をファイルリストに反映しますか？(Enter/Esc):\n"

        def jobCheckEmptyFinished(job_item):

            # ビジーインジケータ Off
            window.clearProgress()

            if job_item.isCanceled():
                print("中断しました.\n")
            else:
                print("Done.\n")

            if job_item.isCanceled():
                return

            result = popResultWindow(window, "検索完了", message[0])
            if not result:
                return

            window.jumpLister(
                pane, lister_Custom(window, "[empty] ", location, result_items)
            )

        job_item = ckit.JobItem(jobCheckEmpty, jobCheckEmptyFinished)
        window.taskEnqueue(job_item, "CheckEmpty")

    # https://github.com/crftwr/cfiler/blob/0d1017e93939b53024b9ba80492c428d3ae24b8b/_config.py#L361
    def command_CheckDuplicate(_):

        left_pane = window.leftPane()
        right_pane = window.rightPane()

        left_location = window.leftFileList().getLocation()
        right_location = window.rightFileList().getLocation()

        left_items = window.leftItems()
        right_items = window.rightItems()

        items = []
        for item in left_items:
            if not item.isdir() and hasattr(item, "getFullpath"):
                items.append([item, None, False])
        for item in right_items:
            if not item.isdir() and hasattr(item, "getFullpath"):
                items.append([item, None, False])

        if len(items) <= 1:
            return

        result_left_items = set()
        result_right_items = set()
        message = [""]

        def jobCheckDuplicate(job_item):

            def printBoth(s):
                print(s)
                message[0] += s + "\n"

            def appendResult(item):
                if item in left_items:
                    result_left_items.add(item)
                    printBoth("   Left: %s" % item.getName())
                else:
                    result_right_items.add(item)
                    printBoth("  Right: %s" % item.getName())

            def leftOrRight(item):
                if item in left_items:
                    return "Left"
                else:
                    return "Right"

            printBoth("重複するファイルを検索 :")

            # ビジーインジケータ On
            window.setProgressValue(None)

            for i, item in enumerate(items):

                if job_item.isCanceled():
                    break
                if job_item.waitPaused():
                    window.setProgressValue(None)

                digest = hashlib.md5(item[0].open().read(64 * 1024)).hexdigest()
                print("MD5 : %s : %s" % (item[0].getName(), digest))
                items[i][1] = digest

            # ファイルサイズとハッシュでソート
            if not job_item.isCanceled():
                items.sort(key=lambda item: (item[0].size(), item[1]))

            for i in range(len(items)):

                if job_item.isCanceled():
                    break
                if job_item.waitPaused():
                    window.setProgressValue(None)

                item1 = items[i]
                if item1[2]:
                    continue

                dumplicate_items = []
                dumplicate_filenames = [item1[0].getFullpath()]

                for k in range(i + 1, len(items)):

                    if job_item.isCanceled():
                        break
                    if job_item.waitPaused():
                        window.setProgressValue(None)

                    item2 = items[k]
                    if item1[1] != item2[1]:
                        break
                    if item2[2]:
                        continue
                    if item2[0].getFullpath() in dumplicate_filenames:
                        item2[2] = True
                        continue

                    print(
                        "比較 : %5s : %s" % (leftOrRight(item1[0]), item1[0].getName())
                    )
                    print(
                        "     : %5s : %s …"
                        % (leftOrRight(item2[0]), item2[0].getName()),
                    )

                    try:
                        result = compareFile(
                            item1[0].getFullpath(),
                            item2[0].getFullpath(),
                            shallow=1,
                            schedule_handler=job_item.isCanceled,
                        )
                    except CanceledError:
                        print("中断")
                        break

                    if result:
                        print("一致")
                        dumplicate_items.append(item2)
                        dumplicate_filenames.append(item2[0].getFullpath())
                        item2[2] = True
                    else:
                        print("不一致")

                    print("")

                if dumplicate_items:
                    appendResult(item1[0])
                    for item2 in dumplicate_items:
                        appendResult(item2[0])
                    printBoth("")

            message[0] += "\n"
            message[0] += "検索結果をファイルリストに反映しますか？(Enter/Esc):\n"

        def jobCheckDuplicateFinished(job_item):

            # ビジーインジケータ Off
            window.clearProgress()

            if job_item.isCanceled():
                print("中断しました.\n")
            else:
                print("Done.\n")

            if job_item.isCanceled():
                return

            result = popResultWindow(window, "検索完了", message[0])
            if not result:
                return

            window.leftJumpLister(
                lister_Custom(
                    window, "[duplicate] ", left_location, list(result_left_items)
                )
            )
            window.rightJumpLister(
                lister_Custom(
                    window, "[duplicate] ", right_location, list(result_right_items)
                )
            )

        job_item = ckit.JobItem(jobCheckDuplicate, jobCheckDuplicateFinished)
        window.taskEnqueue(job_item, "CheckDuplicate")

    def diffinity(_):
        exe_path = Path(USER_PROFILE, r"scoop\apps\diffinity\current\Diffinity.exe")
        if not exe_path.exists():
            print("cannnot find diffinity.exe...")
            return

        left_pane = LeftPane(window)
        left_selcted = left_pane.selectedItemPaths
        if len(left_selcted) != 1:
            print("select just 1 file on left pane.")
            return
        left_path = Path(left_selcted[0])
        if not left_path.is_file():
            print("selected item on left pane is not comparable.")
            return
        left_pane = LeftPane(window)

        right_pane = RightPane(window)
        right_selcted = right_pane.selectedItemPaths
        if len(right_selcted) != 1:
            print("select just 1 file on right pane.")
            return
        right_path = Path(right_selcted[0])
        if not right_path.is_file():
            print("selected item on right pane is not comparable.")
            return

        param = '"{}" "{}"'.format(left_path, right_path)
        pyauto.shellExecute(None, str(exe_path), param, "")

    def select_dupl(_):
        inactive = CPane(window, False)
        other_names = inactive.names
        pane = CPane(window)
        for i in range(pane.count):
            item = pane.byIndex(i)
            if item.getName() in other_names:
                pane.select(i)
            else:
                pane.unSelect(i)
        pane.refresh()

    def select_unique(_):
        inactive = CPane(window, False)
        other_names = inactive.names
        pane = CPane(window)
        for i in range(pane.count):
            item = pane.byIndex(i)
            if item.getName() in other_names:
                pane.unSelect(i)
            else:
                pane.select(i)
        pane.refresh()

    window.launcher.command_list += [
        ("Diffinity", diffinity),
        ("SelectUnique", select_unique),
        ("SelectDupl", select_dupl),
        ("CheckEmpty", command_CheckEmpty),
        ("CheckDuplicate", command_CheckDuplicate),
    ]

    """


    # --------------------------------------------------------------------

    # ; キーで表示されるフィルタリスト
    window.filter_list += [
        ( "ALL",               filter_Default( "*" ) ),
        ( "SOURCE",            filter_Default( "*.cpp *.c *.h *.cs *.py *.pyw *.fx" ) ),
        ( "BOOKMARK",          filter_Bookmark() ),
    ]

    # --------------------------------------------------------------------
    # " キーで表示されるフィルタ選択リスト

    window.select_filter_list += [
        ( "SOURCE",        filter_Default( "*.cpp *.c *.h *.cs *.py *.pyw *.fx", dir_policy=None ) ),
        ( "BOOKMARK",      filter_Bookmark(dir_policy=None) ),
    ]


    """
