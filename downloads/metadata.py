"""Safe filesystem metadata extraction for Hermes V5 Download Brain."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict


def iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def collect_metadata(path: str | Path) -> Dict[str, Any]:
    file_path = Path(path).expanduser().resolve()
    stat = file_path.stat()
    return {
        "filename": file_path.name,
        "path": str(file_path),
        "extension": file_path.suffix.lower(),
        "size_bytes": stat.st_size,
        "created_at": iso_from_timestamp(getattr(stat, "st_birthtime", stat.st_ctime)),
        "modified_at": iso_from_timestamp(stat.st_mtime),
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "is_hidden": file_path.name.startswith("."),
    }


def is_safe_regular_file(path: str | Path) -> bool:
    file_path = Path(path)
    try:
        return file_path.is_file() and not file_path.is_symlink()
    except OSError:
        return False


def default_downloads_dir() -> Path:
    configured = os.environ.get("HERMES_DOWNLOADS_DIR")
    if configured:
        return Path(configured).expanduser()
    return Path.home() / "Downloads"
