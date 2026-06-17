"""Persistent processing queue for Hermes V5 Download Brain."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

QUEUE_STATUSES = {"new", "processing", "complete", "archived", "error"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class DownloadQueue:
    def __init__(self, path: str | Path = "memory/downloads_queue.json"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def load(self) -> Dict[str, Any]:
        if not self.path.exists():
            return {"version": 1, "updated_at": utc_now(), "items": []}
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            data.setdefault("version", 1)
            data.setdefault("items", [])
            return data
        except json.JSONDecodeError:
            backup = self.path.with_suffix(".corrupt.json")
            self.path.replace(backup)
            return {"version": 1, "updated_at": utc_now(), "items": []}

    def save(self, data: Dict[str, Any]) -> None:
        data["updated_at"] = utc_now()
        with self.path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)

    def upsert_many(self, items: Iterable[Dict[str, Any]]) -> Dict[str, int]:
        data = self.load()
        existing = {item["path"]: item for item in data.get("items", []) if "path" in item}
        created = 0
        updated = 0
        for item in items:
            path = item["path"]
            if path in existing:
                preserved_status = existing[path].get("status", "new")
                existing[path].update(item)
                existing[path]["status"] = preserved_status
                existing[path]["last_seen_at"] = utc_now()
                updated += 1
            else:
                item = dict(item)
                item.setdefault("status", "new")
                item.setdefault("first_seen_at", utc_now())
                item.setdefault("last_seen_at", utc_now())
                existing[path] = item
                created += 1
        data["items"] = sorted(existing.values(), key=lambda value: value.get("modified_at", ""), reverse=True)
        self.save(data)
        return {"created": created, "updated": updated, "total": len(data["items"])}

    def set_status(self, path: str, status: str) -> bool:
        if status not in QUEUE_STATUSES:
            raise ValueError(f"Unknown queue status: {status}")
        data = self.load()
        for item in data.get("items", []):
            if item.get("path") == path:
                item["status"] = status
                item["status_updated_at"] = utc_now()
                self.save(data)
                return True
        return False

    def items(self, status: str | None = None) -> List[Dict[str, Any]]:
        data = self.load()
        items = data.get("items", [])
        if status is None:
            return items
        return [item for item in items if item.get("status") == status]
