import datetime
import os
from pathlib import Path
import hashlib

import ckit
import pyauto

from cfiler import *
from cfiler_mainwindow import MainWindow, PAINT_FOCUSED_ITEMS, PAINT_FOCUSED_HEADER
from cfiler_filelist import FileList, item_Base

USER_PROFILE = os.environ.get("USERPROFILE") or ""
LINE_BREAK = os.linesep


# https://github.com/crftwr/cfiler/blob/master/cfiler_mainwindow.py
def configure(window: MainWindow):

    window.keymap["C-H"] = window.command_JumpHistory
    window.keymap["C-D"] = window.command_Delete

    window.keymap["J"] = window.command_CursorDown
    window.keymap["K"] = window.command_CursorUp
    window.keymap["C-J"] = window.command_CursorDownSelected
    window.keymap["C-K"] = window.command_CursorUpSelected

    class ActivePane:
        def __init__(self, window: MainWindow) -> None:
            self._pane = window.activePane()

        @property
        def cursor(self) -> int:
            return self._pane.cursor

        @property
        def file_list(self) -> FileList:
            return self._pane.file_list

        @property
        def current_path(self) -> str:
            return self.file_list.getLocation()

        @property
        def count(self) -> int:
            return self.file_list.numItems()

        def byIndex(self, i: int) -> item_Base:
            return self.file_list.getItem(i)

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

    def smart_copy_path():
        pane = ActivePane(window)
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

    def command_SmartCopyPath(_):
        smart_copy_path()

    window.keymap["C-A-P"] = command_SmartCopyPath

    def smart_enter():
        pane = ActivePane(window)
        if pane.focusItem.isdir():
            window.command.Enter()
        else:
            window.command.Execute()

    def command_SmartEnter(_):
        smart_enter()

    window.keymap["L"] = command_SmartEnter
    window.keymap["H"] = window.command_GotoParentDir

    class Selector:
        def __init__(self, window: MainWindow) -> None:
            self._window = window

        @property
        def pane(self) -> ActivePane:
            return ActivePane(self._window)

        def mark(self) -> None:
            self._window.paint(PAINT_FOCUSED_ITEMS | PAINT_FOCUSED_HEADER)

        def allItems(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                pane.select(i)
            self.mark()

        def allFiles(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if not pane.byIndex(i).isdir():
                    pane.select(i)
            self.mark()

        def allDirs(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                if pane.byIndex(i).isdir():
                    pane.select(i)
            self.mark()

        def clearAll(self) -> None:
            pane = self.pane
            for i in range(pane.count):
                pane.unSelect(i)
            self.mark()

    SELECTOR = Selector(window)

    def command_SelectAllItems(_):
        SELECTOR.allItems()

    window.keymap["A"] = command_SelectAllItems

    def command_UnSelectAllItems(_):
        SELECTOR.clearAll()

    window.keymap["S-A"] = command_UnSelectAllItems

    def command_SelectAllFiles(_):
        SELECTOR.allFiles()

    window.keymap["F"] = command_SelectAllFiles

    def command_SelectAllDirs(_):
        SELECTOR.allDirs()

    window.keymap["D"] = command_SelectAllDirs

    def open_parent_side():
        pass

    def command_OpenParentSide(_):
        pass

    def duplicate_with_name():
        pass

    def command_DuplicateWithName(_):
        pass

    window.keymap["A-C"] = window.command_ContextMenu
    window.keymap["A-S-C"] = window.command_ContextMenuDir

    def reload_config(_):
        window.configure()
        ts = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
        print("{} reloaded config.py\n".format(ts))

    window.keymap["C-A-R"] = reload_config

    def open_doc(_):
        help_path = str(Path(ckit.getAppExePath(), "doc", "index.html"))
        pyauto.shellExecute(None, help_path, "", "")

    window.keymap["A-H"] = open_doc

    def open_source(_):
        pyauto.shellExecute(
            None,
            "https://github.com/crftwr/cfiler/blob/master/cfiler_mainwindow.py",
            "",
            "",
        )

    window.keymap["A-S-H"] = open_source

    def edit_config(_):
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

    window.keymap["C-E"] = edit_config

    # https://github.com/crftwr/cfiler/blob/_config.py#L284
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

    # https://github.com/crftwr/cfiler/blob/_config.py#L361
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

    window.launcher.command_list += [
        ("CheckEmpty", command_CheckEmpty),
        ("CheckDuplicate", command_CheckDuplicate),
    ]

    """
    # ↓デフォルトの_config.pyをコメントアウト

    # --------------------------------------------------------------------
    # F5 キーであふを起動する

    def command_LaunchAFX(info):
        print( "あふを起動 :" )
        left_location = os.path.join( window.leftFileList().getLocation(), "" )
        right_location = os.path.join( window.rightFileList().getLocation(), "" )
        print( "  Left  :", left_location )
        print( "  Right :", right_location )
        shellExecute( None, "c:/ols/afx/afx.exe", '-L"%s" -R"%s"' % (left_location,right_location), "" )
        print( "Done.\n" )

    window.keymap[ "F5" ] = command_LaunchAFX

    # --------------------------------------------------------------------
    # Shift-X キーでプログラム起動メニューを表示する

    def command_ProgramMenu(info):

        def launch_InternetExplorer():
            shellExecute( None, r"C:\Program Files\Internet Explorer\iexplore.exe", "", "" )

        def launch_CommandPrompt():
            shellExecute( None, r"cmd.exe", "", window.activeFileList().getLocation() )

        items = [
            ( "Internet Explorer", launch_InternetExplorer ),
            ( "Command Prompt",    launch_CommandPrompt )
        ]

        result = popMenu( window, "プログラム", items, 0 )
        if result<0 : return
        items[result][1]()

    window.keymap[ "S-X" ] = command_ProgramMenu

    # --------------------------------------------------------------------
    # Enter キーを押したときの動作をカスタマイズするためのフック

    def hook_Enter():

        if 0:
            print( "hook_Enter" )
            pane = window.activePane()
            item = pane.file_list.getItem(pane.cursor)

            # hook から True を返すと、デフォルトの動作がスキップされます
            return True

    window.enter_hook = hook_Enter

    # --------------------------------------------------------------------
    # テキストエディタを設定する

    if 1: # プログラムのファイルパスを設定 (単純な使用方法)
        window.editor = "notepad.exe"

    if 0: # 呼び出し可能オブジェクトを設定 (高度な使用方法)
        def editor( item, point, location ):
            shellExecute( None, "lredit.exe", '--text "%s" %d:%d' % ( item.getFullpath(), point[0], point[1] ), location )
        window.editor = editor

    # --------------------------------------------------------------------
    # テキスト差分エディタを設定する
    #
    #   この例では外部テキストマージツールとして、WinMerge( http://winmerge.org/ )
    #   を使用しています。
    #   必要に応じてインストールしてください。

    if 0: # プログラムのファイルパスを設定 (単純な使用方法)
        window.diff_editor = "c:\\ols\\winmerge\\WinMergeU.exe"

    if 0: # 呼び出し可能オブジェクトを設定 (高度な使用方法)
        def diffEditor( left_item, right_item, location ):
            shellExecute( None, "c:\\ols\\winmerge\\WinMergeU.exe", '"%s" "%s"'% ( left_item.getFullpath(), right_item.getFullpath() ), location )
        window.diff_editor = diffEditor

    # --------------------------------------------------------------------
    # J キーで表示されるジャンプリスト

    window.jump_list += [
        ( "OLS",       "c:\\ols" ),
        ( "PROJECT",   "c:\\project" ),
        ( "MUSIC",     "e:\\music" ),
    ]

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

    # --------------------------------------------------------------------
    # アーカイブファイルのファイル名パターンとアーカイバの関連付け

    window.archiver_list = [
        ( "*.zip *.jar *.apk",  ZipArchiver ),
        ( "*.7z",               SevenZipArchiver ),
        ( "*.tgz *.tar.gz",     TgzArchiver ),
        ( "*.tbz2 *.tar.bz2",   Bz2Archiver ),
        ( "*.lzh",              LhaArchiver ),
        ( "*.rar",              RarArchiver ),
    ]

    # --------------------------------------------------------------------
    # ソースファイルでEnterされたときの関連付け処理

    def association_Video(item):
        shellExecute( None, r"wmplayer.exe", '/prefetch:7 /Play "%s"' % item.getFullpath(), "" )

    window.association_list += [
        ( "*.mpg *.mpeg *.avi *.wmv", association_Video ),
    ]


    # --------------------------------------------------------------------
    # ファイルアイテムの表示形式

    # 昨日以前については日時、今日については時間、を表示するアイテムの表示形式
    #
    #   引数:
    #       window   : メインウインドウ
    #       item     : アイテムオブジェクト
    #       width    : 表示領域の幅
    #       userdata : ファイルリストの描画中に一貫して使われるユーザデータオブジェクト
    #
    def itemformat_Name_Ext_Size_YYYYMMDDorHHMMSS( window, item, width, userdata ):

        if item.isdir():
            str_size = "<DIR>"
        else:
            str_size = "%6s" % getFileSizeString(item.size())

        if not hasattr(userdata,"now"):
            userdata.now = time.localtime()

        t = item.time()
        if t[0]==userdata.now[0] and t[1]==userdata.now[1] and t[2]==userdata.now[2]:
            str_time = "  %02d:%02d:%02d" % ( t[3], t[4], t[5] )
        else:
            str_time = "%04d/%02d/%02d" % ( t[0]%10000, t[1], t[2] )

        str_size_time = "%s %s" % ( str_size, str_time )

        width = max(40,width)
        filename_width = width-len(str_size_time)

        if item.isdir():
            body, ext = item.getNameNfc(), None
        else:
            body, ext = splitExt(item.getNameNfc())

        if ext:
            body_width = min(width,filename_width-6)
            return ( adjustStringWidth(window,body,body_width,ALIGN_LEFT,ELLIPSIS_RIGHT)
                   + adjustStringWidth(window,ext,6,ALIGN_LEFT,ELLIPSIS_NONE)
                   + str_size_time )
        else:
            return ( adjustStringWidth(window,body,filename_width,ALIGN_LEFT,ELLIPSIS_RIGHT)
                   + str_size_time )

    # Z キーで表示されるファイル表示形式リスト
    window.itemformat_list = [
        ( "1 : 全て表示 : filename  .ext  99.9K YY/MM/DD HH:MM:SS", itemformat_Name_Ext_Size_YYMMDD_HHMMSS ),
        ( "2 : 秒を省略 : filename  .ext  99.9K YY/MM/DD HH:MM",    itemformat_Name_Ext_Size_YYMMDD_HHMM ),
        ( "3 : 日 or 時 : filename  .ext  99.9K YYYY/MM/DD",        itemformat_Name_Ext_Size_YYYYMMDDorHHMMSS ),
        ( "0 : 名前のみ : filename.ext",                            itemformat_NameExt ),
    ]

    # 表示形式の初期設定
    window.itemformat = itemformat_Name_Ext_Size_YYYYMMDDorHHMMSS

    # --------------------------------------------------------------------
    # "Google" コマンド
    #   Google でキーワードを検索します

    def command_Google(info):
        if len(info.args)>=1:
            keyword = ' '.join(info.args)
            keyword = urllib.parse.quote_plus(keyword)
        else:
            keyword = ""
        url = "http://www.google.com/search?ie=utf8&q=%s" % keyword
        shellExecute( None, url, "", "" )

    # --------------------------------------------------------------------
    # "Eijiro" コマンド
    #   英辞郎 on the WEB で日本語/英語を相互に検索します

    def command_Eijiro(info):
        if len(args)>=1:
            keyword = ' '.join(info.args)
            keyword = urllib.parse.quote_plus(keyword)
        else:
            keyword = ""
        url = "http://eow.alc.co.jp/%s/UTF-8/" % keyword
        shellExecute( None, url, "", "" )

    # --------------------------------------------------------------------
    # "Subst" コマンド
    #   任意のパスにドライブを割り当てるか、ドライブの解除を行います。
    #    subst;H;C:\dirname  : C:\dirname を Hドライブに割り当てます
    #    subst;H             : Hドライブの割り当てを解除します

    def command_Subst(info):

        if len(info.args)>=1:
            drive_letter = info.args[0]
            if len(info.args)>=2:
                path = info.args[1]
                if window.subProcessCall( [ "subst", drive_letter+":", os.path.normpath(path) ], cwd=None, env=None, enable_cancel=False )==0:
                    print( "%s に %sドライブを割り当てました。" % ( path, drive_letter ) )
            else:
                if window.subProcessCall( [ "subst", drive_letter+":", "/D" ], cwd=None, env=None, enable_cancel=False )==0:
                    print( "%sドライブの割り当てを解除しました。" % ( drive_letter ) )
        else:
            print( "ドライブの割り当て : Subst;<ドライブ名>;<パス>" )
            print( "ドライブの解除     : Subst;<ドライブ名>" )
            raise TypeError


    # --------------------------------------------------------------------
    # Subversionでバージョン管理しているファイルだけを表示するフィルタ
    class filter_Subversion:

        svn_exe_path = "c:/Program Files/TortoiseSVN/bin/svn.exe"

        def __init__( self, nonsvn_dir_policy ):

            self.nonsvn_dir_policy = nonsvn_dir_policy
            self.cache = {}
            self.last_used = time.time()

        def _getSvnFiles( self, dirname ):

            if dirname.replace("\\","/").find("/.svn/") >= 0:
                return set()

            filename_set = set()

            cmd = [ filter_Subversion.svn_exe_path, "stat", "-q", "-v", "--xml", "--depth", "immediates" ]
            svn_output = io.StringIO()
            subprocess = SubProcess( cmd, cwd=dirname, env=None, stdout_write=svn_output.write )
            subprocess()

            try:
                elm1 = xml.etree.ElementTree.fromstring(svn_output.getvalue())
            except xml.etree.ElementTree.ParseError as e:
                for line in svn_output.getvalue().splitlines():
                    if line.startswith("svn:"):
                        print( line )
                return filename_set
            elm2 = elm1.find("target")
            for elm3 in elm2.findall("entry"):
                elm4 = elm3.find("wc-status")
                if elm4.get("item")=="unversioned": continue
                filename_set.add( elm3.get("path") )

            return filename_set

        def __call__( self, item ):

            now = time.time()
            if now - self.last_used > 3.0:
                self.cache = {}
            self.last_used = now

            if not hasattr(item,"getFullpath"): return False

            fullpath = item.getFullpath()

            dirname, filename = os.path.split(fullpath)

            try:
                filename_set = self.cache[dirname]
            except KeyError:
                filename_set = self._getSvnFiles(dirname)
                self.cache[dirname] = filename_set

            if item.isdir() and not filename_set:
                return self.nonsvn_dir_policy
            return filename in filename_set

        def __str__(self):
            return "[svn]"

    window.filter_list += [
        ( "SUBVERSION",    filter_Subversion( nonsvn_dir_policy=True ) ),
    ]

    window.select_filter_list += [
        ( "SUBVERSION",    filter_Subversion( nonsvn_dir_policy=False ) ),
    ]

    # --------------------------------------------------------------------


# テキストビューアの設定処理
def configure_TextViewer(window):

    # --------------------------------------------------------------------
    # F1 キーでヘルプファイルを表示する

    def command_Help(info):
        print( "Helpを起動 :" )
        help_path = os.path.join( getAppExePath(), 'doc\\index.html' )
        shellExecute( None, help_path, "", "" )
        print( "Done.\n" )

    window.keymap[ "F1" ] = command_Help


# テキスト差分ビューアの設定処理
def configure_DiffViewer(window):

    # --------------------------------------------------------------------
    # F1 キーでヘルプファイルを表示する

    def command_Help(info):
        print( "Helpを起動 :" )
        help_path = os.path.join( getAppExePath(), 'doc\\index.html' )
        shellExecute( None, help_path, "", "" )
        print( "Done.\n" )

    window.keymap[ "F1" ] = command_Help


# イメージビューアの設定処理
def configure_ImageViewer(window):

    # --------------------------------------------------------------------
    # F1 キーでヘルプファイルを表示する

    def command_Help(info):
        print( "Helpを起動 :" )
        help_path = os.path.join( getAppExePath(), 'doc\\index.html' )
        shellExecute( None, help_path, "", "" )
        print( "Done.\n" )

    window.keymap[ "F1" ] = command_Help


# リストウインドウの設定処理
def configure_ListWindow(window):

    # --------------------------------------------------------------------
    # F1 キーでヘルプファイルを表示する

    def command_Help(info):
        print( "Helpを起動 :" )
        help_path = os.path.join( getAppExePath(), 'doc\\index.html' )
        shellExecute( None, help_path, "", "" )
        print( "Done.\n" )

    window.keymap[ "F1" ] = command_Help
    """
