import os
import shutil
import subprocess
from pathlib import Path


def is_junction(p: Path):
    try:
        return bool(
            os.lstat(p).st_file_attributes & 0x400
        )  # FILE_ATTRIBUTE_REPARSE_POINT
    except (OSError, AttributeError):
        return False


def make_junction() -> None:
    d = "CraftFiler"
    data_path = Path(os.environ["USERPROFILE"]) / d
    src_path = Path(__file__).resolve().parent / d

    if data_path.is_symlink() or is_junction(data_path):
        os.rmdir(data_path)
    elif data_path.is_dir():
        shutil.rmtree(data_path, ignore_errors=True)
    elif data_path.exists():
        data_path.unlink()

    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(data_path), str(src_path)],
        check=True,
    )


if __name__ == "__main__":
    make_junction()
