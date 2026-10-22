from __future__ import annotations

import os
import sys
from pathlib import Path


def _windows_downloads() -> Path | None:
    try:
        import winreg
    except ImportError:
        return None

    key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
    downloads_guid = "{374DE290-123F-4565-9164-39C4925E467B}"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _ = winreg.QueryValueEx(key, downloads_guid)
    except OSError:
        return None
    return Path(os.path.expandvars(value)).expanduser()


def _linux_downloads() -> Path | None:
    user_dirs = Path.home() / ".config" / "user-dirs.dirs"
    if not user_dirs.is_file():
        return None

    try:
        for line in user_dirs.read_text(encoding="utf-8").splitlines():
            if not line.startswith("XDG_DOWNLOAD_DIR="):
                continue
            raw = line.split("=", 1)[1].strip().strip('"')
            raw = raw.replace("$HOME", str(Path.home()))
            return Path(raw).expanduser()
    except OSError:
        return None
    return None


def detect_downloads_directory() -> Path:
    """Return the best available Downloads directory for the current platform."""
    candidate: Path | None = None
    if sys.platform.startswith("win"):
        candidate = _windows_downloads()
    elif sys.platform.startswith("linux"):
        candidate = _linux_downloads()

    return (candidate or (Path.home() / "Downloads")).expanduser()
