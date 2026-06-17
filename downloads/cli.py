"""CLI helpers for Hermes V5 Download Brain."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .intake import run_download_intake
from .queue import DownloadQueue


def print_json(payload: Dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def handle_download_command(args: list[str]) -> Dict[str, Any]:
    command = args[0] if args else "scan"
    if command in {"scan", "intake", "run"}:
        downloads_dir = Path(args[1]).expanduser() if len(args) > 1 else None
        return run_download_intake(downloads_dir=downloads_dir)
    if command == "queue":
        status = args[1] if len(args) > 1 else None
        queue = DownloadQueue()
        return {"items": queue.items(status=status)}
    if command == "status":
        queue = DownloadQueue()
        items = queue.items()
        counts: Dict[str, int] = {}
        for item in items:
            status = item.get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
        return {"total": len(items), "by_status": counts}
    return {
        "error": "unknown_download_command",
        "supported": ["scan", "intake", "run", "queue", "status"],
    }
