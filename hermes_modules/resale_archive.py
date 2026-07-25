from __future__ import annotations

import argparse
import csv
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable


STATUSES = {"CAPTURED", "RESEARCH", "READY", "POSTED", "SOLD", "HOLD", "FIX"}
ACTION_STATUS = {
    "research": "RESEARCH",
    "retake-photo": "FIX",
    "clean": "FIX",
    "fix": "FIX",
    "approve": "READY",
    "post-ready": "READY",
    "pack": "POSTED",
    "dispatch": "SOLD",
    "hold": "HOLD",
    "exit": "HOLD",
}
JSON_FIELDS = {"photo_refs", "identifiers"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def default_database_path() -> Path:
    root = Path(os.environ.get("HERMES_DATA_DIR", Path.home() / ".hermes"))
    return root / "resale" / "archive.sqlite3"


class ResaleArchive:
    """Durable, deterministic, local-only resale inventory."""

    def __init__(self, database: str | Path | None = None) -> None:
        self.database = Path(database) if database else default_database_path()
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(self.database)
        self.connection.row_factory = sqlite3.Row
        self._initialize()

    def close(self) -> None:
        self.connection.close()

    def _initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS resale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                category TEXT NOT NULL,
                photo_refs TEXT NOT NULL DEFAULT '[]',
                identifiers TEXT NOT NULL DEFAULT '{}',
                item_condition TEXT NOT NULL DEFAULT '',
                research_confidence REAL NOT NULL DEFAULT 0,
                price_min REAL NOT NULL DEFAULT 0,
                price_max REAL NOT NULL DEFAULT 0,
                target_price REAL NOT NULL DEFAULT 0,
                platform TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'CAPTURED',
                priority INTEGER NOT NULL DEFAULT 0,
                urgency INTEGER NOT NULL DEFAULT 0,
                effort INTEGER NOT NULL DEFAULT 1,
                provenance TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                sold_at TEXT,
                sold_price REAL
            );
            CREATE INDEX IF NOT EXISTS resale_items_status_idx
                ON resale_items(status, priority, updated_at);
            """
        )
        self.connection.commit()

    @staticmethod
    def _validate(item: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(item)
        normalized["title"] = str(normalized.get("title", "")).strip()
        normalized["category"] = str(normalized.get("category", "")).strip()
        normalized["provenance"] = str(normalized.get("provenance", "")).strip()
        if not all((normalized["title"], normalized["category"], normalized["provenance"])):
            raise ValueError("title, category, and provenance are required")
        status = str(normalized.get("status", "CAPTURED")).upper()
        if status not in STATUSES:
            raise ValueError(f"unsupported status: {status}")
        normalized["status"] = status
        confidence = float(normalized.get("research_confidence", 0))
        if not 0 <= confidence <= 1:
            raise ValueError("research_confidence must be between 0 and 1")
        normalized["research_confidence"] = confidence
        for field in ("priority", "urgency", "effort"):
            normalized[field] = int(normalized.get(field, 1 if field == "effort" else 0))
        for field in ("price_min", "price_max", "target_price"):
            normalized[field] = float(normalized.get(field, 0))
        normalized["photo_refs"] = list(normalized.get("photo_refs") or [])
        normalized["identifiers"] = dict(normalized.get("identifiers") or {})
        return normalized

    def capture(self, item: dict[str, Any]) -> int:
        data = self._validate(item)
        timestamp = _now()
        cursor = self.connection.execute(
            """
            INSERT INTO resale_items (
                title, category, photo_refs, identifiers, item_condition,
                research_confidence, price_min, price_max, target_price,
                platform, status, priority, urgency, effort, provenance,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data["title"],
                data["category"],
                json.dumps(data["photo_refs"], sort_keys=True),
                json.dumps(data["identifiers"], sort_keys=True),
                str(data.get("condition", data.get("item_condition", ""))),
                data["research_confidence"],
                data["price_min"],
                data["price_max"],
                data["target_price"],
                str(data.get("platform", "")),
                data["status"],
                data["priority"],
                data["urgency"],
                data["effort"],
                data["provenance"],
                timestamp,
                timestamp,
            ),
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["condition"] = item.pop("item_condition")
        for field in JSON_FIELDS:
            item[field] = json.loads(item[field])
        return item

    def items(self, include_sold: bool = True) -> list[dict[str, Any]]:
        query = "SELECT * FROM resale_items"
        params: tuple[Any, ...] = ()
        if not include_sold:
            query += " WHERE status != ?"
            params = ("SOLD",)
        query += " ORDER BY id"
        return [self._decode(row) for row in self.connection.execute(query, params)]

    def apply_action(
        self,
        item_id: int,
        action: str,
        *,
        sold_price: float | None = None,
    ) -> dict[str, Any]:
        action = action.strip().lower()
        if action not in ACTION_STATUS:
            raise ValueError(f"unsupported action: {action}")
        status = ACTION_STATUS[action]
        sold_at = _now() if status == "SOLD" else None
        self.connection.execute(
            """
            UPDATE resale_items
            SET status = ?, updated_at = ?, sold_at = COALESCE(?, sold_at),
                sold_price = COALESCE(?, sold_price)
            WHERE id = ?
            """,
            (status, _now(), sold_at, sold_price, item_id),
        )
        self.connection.commit()
        row = self.connection.execute(
            "SELECT * FROM resale_items WHERE id = ?", (item_id,)
        ).fetchone()
        if row is None:
            raise KeyError(item_id)
        return self._decode(row)

    @staticmethod
    def _queue_score(item: dict[str, Any]) -> float:
        expected_value = item["target_price"] or (
            item["price_min"] + item["price_max"]
        ) / 2
        readiness = {"READY": 200, "POSTED": 120, "RESEARCH": 40, "FIX": 10}.get(
            item["status"], 0
        )
        return round(
            readiness
            + item["urgency"] * 100
            + item["priority"] * 20
            + item["research_confidence"] * 50
            + expected_value / 10
            - item["effort"] * 10,
            4,
        )

    def daily_queue(self, limit: int = 25) -> list[dict[str, Any]]:
        candidates = [
            item for item in self.items() if item["status"] not in {"SOLD", "HOLD"}
        ]
        for item in candidates:
            item["queue_score"] = self._queue_score(item)
        candidates.sort(
            key=lambda item: (
                -item["queue_score"],
                item["created_at"],
                item["id"],
            )
        )
        return candidates[:limit]

    def export_json(self, path: str | Path) -> Path:
        target = Path(path)
        target.write_text(
            json.dumps(self.items(), indent=2, sort_keys=True), encoding="utf-8"
        )
        return target

    def export_csv(self, path: str | Path) -> Path:
        target = Path(path)
        rows = self.items()
        fields = list(rows[0]) if rows else [
            "title",
            "category",
            "status",
            "provenance",
        ]
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow(
                    {
                        key: json.dumps(value, sort_keys=True)
                        if key in JSON_FIELDS
                        else value
                        for key, value in row.items()
                    }
                )
        return target

    def import_records(self, records: Iterable[dict[str, Any]]) -> list[int]:
        return [self.capture(record) for record in records]

    def import_json(self, path: str | Path) -> list[int]:
        records = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(records, list):
            raise ValueError("JSON import must contain a list")
        return self.import_records(records)

    def import_csv(self, path: str | Path) -> list[int]:
        with Path(path).open(encoding="utf-8", newline="") as handle:
            records = list(csv.DictReader(handle))
        for record in records:
            for field in JSON_FIELDS:
                record[field] = json.loads(record.get(field) or "[]" if field == "photo_refs" else "{}")
        return self.import_records(records)

    def summary(self, days: int, monthly_target: float = 0) -> dict[str, Any]:
        since = datetime.now(UTC) - timedelta(days=days)
        sold = [
            item
            for item in self.items()
            if item["sold_at"]
            and datetime.fromisoformat(item["sold_at"]) >= since
        ]
        revenue = round(sum(item["sold_price"] or 0 for item in sold), 2)
        sale_days = [
            (
                datetime.fromisoformat(item["sold_at"])
                - datetime.fromisoformat(item["created_at"])
            ).total_seconds()
            / 86400
            for item in sold
        ]
        return {
            "days": days,
            "sold_count": len(sold),
            "revenue": revenue,
            "average_sale_days": round(sum(sale_days) / len(sale_days), 2)
            if sale_days
            else None,
            "monthly_target": monthly_target,
            "target_progress": round(revenue / monthly_target, 4)
            if monthly_target
            else None,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Hermes local resale archive")
    parser.add_argument("--database", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    capture = sub.add_parser("capture")
    capture.add_argument("json_file", type=Path)
    sub.add_parser("queue")
    summary = sub.add_parser("summary")
    summary.add_argument("--days", type=int, default=30)
    export = sub.add_parser("export")
    export.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    archive = ResaleArchive(args.database)
    if args.command == "capture":
        print(archive.capture(json.loads(args.json_file.read_text(encoding="utf-8"))))
    elif args.command == "queue":
        print(json.dumps(archive.daily_queue(), indent=2))
    elif args.command == "summary":
        print(json.dumps(archive.summary(args.days), indent=2))
    elif args.command == "export":
        archive.export_csv(args.path) if args.path.suffix == ".csv" else archive.export_json(args.path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
