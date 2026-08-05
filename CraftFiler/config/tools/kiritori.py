from .common import get_now


def setup(_window) -> None:
    global window  # ty: ignore[unresolved-global]
    window = _window


_sep = "-"


def get_timestamp() -> str:
    return get_now().strftime(f" %Y-%m-%d %H:%M:%S.%f {_sep * 2}")


def draw_header(title: str) -> None:
    print(f"{get_timestamp().ljust(window.width(), _sep)}\n\n{title}\n")


def draw_footer() -> None:
    print(f"{get_timestamp().rjust(window.width(), _sep)}\n")


def log(s) -> None:
    draw_header(s)
    draw_footer()
