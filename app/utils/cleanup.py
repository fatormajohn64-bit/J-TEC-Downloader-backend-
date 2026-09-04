"""
J TEC Downloader
Temporary download cleanup utilities.
"""

import time
from pathlib import Path

from app.config import settings


def cleanup_old_downloads() -> int:
    """
    Remove temporary files older than the configured lifetime.

    Returns:
        Number of files removed.
    """

    download_dir = Path(settings.temp_download_dir)

    if not download_dir.exists():
        return 0

    now = time.time()
    removed = 0

    for file_path in download_dir.iterdir():
        if not file_path.is_file():
            continue

        try:
            age = now - file_path.stat().st_mtime

            if age > settings.cleanup_after_seconds:
                file_path.unlink()
                removed += 1

        except (FileNotFoundError, PermissionError, OSError):
            continue

    return removed


def cleanup_all_downloads() -> int:
    """
    Remove ALL temporary downloaded files immediately.

    This is intended to be called after a download has
    successfully been delivered to the user.

    Returns:
        Number of files removed.
    """

    download_dir = Path(settings.temp_download_dir)

    if not download_dir.exists():
        return 0

    removed = 0

    for file_path in download_dir.iterdir():
        if not file_path.is_file():
            continue

        try:
            file_path.unlink()
            removed += 1

        except (FileNotFoundError, PermissionError, OSError):
            continue

    return removed
