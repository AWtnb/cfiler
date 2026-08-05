from winreg import HKEY_CLASSES_ROOT, HKEY_CURRENT_USER, OpenKey, QueryValueEx


def get_default_browser() -> str:
    prog_id = None

    def _set_prog_id() -> None:
        registry_paths = [
            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoiceLatest\ProgId",
            r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice",
        ]
        for path in registry_paths:
            try:
                with OpenKey(HKEY_CURRENT_USER, path) as key:
                    nonlocal prog_id
                    prog_id = str(QueryValueEx(key, "ProgId")[0])
            except Exception:  # noqa: BLE001, S110
                pass

    _set_prog_id()
    if not prog_id:
        print("Failed to define default browser by registry ProgId.")
        return ""

    commandline = None

    def _set_commandline() -> None:
        register_path = rf"{prog_id}\shell\open\command"
        try:
            with OpenKey(HKEY_CLASSES_ROOT, register_path) as key:
                nonlocal commandline
                commandline = str(QueryValueEx(key, "")[0])
        except Exception as e:  # noqa: BLE001
            print(f"Failed to get commandline by registry `{register_path}`\n{e}")

    _set_commandline()
    if not commandline:
        return ""

    ext = ".exe"
    return commandline[: commandline.find(ext) + len(ext)].strip('"')
