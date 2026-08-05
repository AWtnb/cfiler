import configparser

SECTION_NAME = "RENAME_CONFIG"


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window

    try:
        window.ini.add_section(SECTION_NAME)
    except configparser.DuplicateSectionError:
        pass


def register(option_name: str, value: str) -> None:
    window.ini.set(SECTION_NAME, option_name, value)


def get_value(option_name: str) -> str:
    try:
        return window.ini.get(SECTION_NAME, option_name)
    except Exception:  # noqa: BLE001
        return ""
