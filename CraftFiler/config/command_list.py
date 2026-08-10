from __future__ import annotations

import ckit  # type: ignore
from cfiler import *  # type: ignore

from . import style
from .tools import (
    archiver,
    bookmark,
    clipboard,
    clon,
    compare,
    image_magick,
    item_filter,
    keybinder,
    linker,
    misc,
    office,
    pdf,
    selector,
)
from .tools.rename import extension as rename_ext
from .tools.rename import index as rename_index
from .tools.rename import insert as rename_insert
from .tools.rename import photo as rename_photo
from .tools.rename import pseudo_voising as rename_pseudo_voicing
from .tools.rename import regexp as rename_regexp
from .tools.rename import stem as rename_stem
from .tools.rename import substr as rename_substr


def setup(window) -> None:

    archiver.setup(window)
    bookmark.setup(window)
    clipboard.setup(window)
    clon.setup(window)
    compare.setup(window)
    image_magick.setup(window)
    item_filter.setup(window)
    keybinder.setup(window)
    linker.setup(window)
    misc.setup(window)
    office.setup(window)
    pdf.setup(window)
    rename_ext.setup(window)
    rename_index.setup(window)
    rename_insert.setup(window)
    rename_photo.setup(window)
    rename_pseudo_voicing.setup(window)
    rename_regexp.setup(window)
    rename_stem.setup(window)
    rename_substr.setup(window)
    selector.setup(window)
    style.setup(window)

    mapping = {
        "CopyForLLM": misc.make_summarize_on_other,
        "GitInit": misc.git_init,
        "ChangeImageType": image_magick.change_image_type,
        "MakeShortcut": linker.make_shortcut,
        "CleanTempFiles": clon.remove_tempfiles,
        "RenamePhotoFileByExifDate": rename_photo.execute_with_exif,
        "RenameLightroomPhoto": rename_photo.execute_for_lightroom_photo_from_dropbox,
        "ZipSelections": archiver.compress,
        "SetBookmarkAlias": bookmark.set_bookmark_alias,
        "BookmarkHere": bookmark.bookmark_here,
        "DocxToTxt": office.docx_to_txt,
        "EjectCurrentDrive": misc.eject_current_drive,
        "ConcPdfGo": pdf.concatenate_pdf,
        "MakeJunction": linker.make_junction,
        "ResetHotkey": misc.reset_hotkey,
        "UnzipSelections": archiver.extract,
        "HideUnselectedItems": item_filter.hide_unselected,
        "ClearFilter": item_filter.clear_filter,
        "CopyDirTree": clipboard.copy_dir_tree,
        "Diffinity": lambda: compare.diff_files(with_diffinity=True),
        "DiffWithVSCode": lambda: compare.diff_files(with_diffinity=False),
        "MakeInternetShortcut": lambda: linker.make_internet_shortcut(
            ckit.getClipboardText().strip()
        ),
        "RenamePseudoVoicing": rename_pseudo_voicing.execute,
        "RenameIndex": rename_index.execute,
        "RenameInsert": rename_insert.execute,
        "RenameExtension": rename_ext.execute,
        "RenameRegExp": rename_regexp.execute,
        "RenameStem": rename_stem.execute,
        "RenameSubstr": rename_substr.execute,
        "FindSameFile": compare.FileHashDiff(2).compare,
        "FromOtherNames": selector.from_other_names,
        "FromActiveNames": selector.from_active_names,
        "SelectSameName": selector.select_same_name,
        "SelectNameUnique": selector.select_name_unique,
        "SelectNameCommon": selector.select_name_common,
        "SelectStemMatchCase": lambda: selector.select_regexp(True),
        "SelectStemMatch": lambda: selector.select_regexp(False),
        "SelectStemStartsWith": selector.select_stem_startswith,
        "SelectStemEndsWith": selector.select_stem_endswith,
        "SelectStemContains": selector.select_stem_contains,
        "SelectByExtension": selector.select_byext,
    }

    for name, func in mapping.items():
        window.launcher.command_list += [(name, keybinder.wrap(func))]
