from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class OracleStore:
    def __init__(self, data_root: Path):
        self.data_root = Path(data_root)
        self.oracle_root = self.data_root / "oracle_v1"
        self.memory_root = self.data_root / "memory"
        self.oracle_root.mkdir(parents=True, exist_ok=True)
        self.memory_root.mkdir(parents=True, exist_ok=True)
        self._ensure_json_file("events.json", [])
        self._ensure_json_file("confirmations.json", [])
        self._ensure_json_file("notifications.json", [])
        self._ensure_json_file("activity_log.json", [])
        self._ensure_memory_files()

    def _ensure_json_file(self, name: str, default: Any) -> None:
        path = self.oracle_root / name
        if not path.exists():
            path.write_text(json.dumps(default, indent=2) + "\n", encoding="utf-8")

    def _ensure_memory_files(self) -> None:
        structured = self.memory_root / "structured.json"
        if not structured.exists():
            structured.write_text("{}\n", encoding="utf-8")
        logs = self.memory_root / "logs.md"
        if not logs.exists():
            logs.write_text("# Oracle V1 Logs\n", encoding="utf-8")

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return default
        return json.loads(text)

    def _write_json(self, path: Path, payload: Any) -> None:
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def read_events(self) -> list[dict[str, Any]]:
        return self._read_json(self.oracle_root / "events.json", [])

    def write_events(self, items: list[dict[str, Any]]) -> None:
        self._write_json(self.oracle_root / "events.json", items)

    def read_confirmations(self) -> list[dict[str, Any]]:
        return self._read_json(self.oracle_root / "confirmations.json", [])

    def write_confirmations(self, items: list[dict[str, Any]]) -> None:
        self._write_json(self.oracle_root / "confirmations.json", items)

    def read_notifications(self) -> list[dict[str, Any]]:
        return self._read_json(self.oracle_root / "notifications.json", [])

    def write_notifications(self, items: list[dict[str, Any]]) -> None:
        self._write_json(self.oracle_root / "notifications.json", items)

    def read_activity_log(self) -> list[dict[str, Any]]:
        return self._read_json(self.oracle_root / "activity_log.json", [])

    def write_activity_log(self, items: list[dict[str, Any]]) -> None:
        self._write_json(self.oracle_root / "activity_log.json", items)

    def read_structured_memory(self) -> dict[str, Any]:
        return self._read_json(self.memory_root / "structured.json", {})

    def write_structured_memory(self, payload: dict[str, Any]) -> None:
        self._write_json(self.memory_root / "structured.json", payload)

    def append_markdown_log(self, heading: str, message: str) -> None:
        timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
        path = self.memory_root / "logs.md"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"\n## {timestamp}\n- kind: {heading}\n- message: {message}\n")

