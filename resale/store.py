from __future__ import annotations

import csv
import io
import json
import os
import sqlite3
from dataclasses import fields
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Iterable

from resale.models import Item, ItemStatus, Priority, utc_now


JSON_FIELDS = {"identifiers", "source_refs", "photo_refs"}


def default_database_path() -> Path:
    configured = os.environ.get("HERMES_DATA_DIR", "").strip()
    root = Path(configured).expanduser() if configured else Path.home() / ".hermes"
    return root / "resale" / "inventory.sqlite3"


class InventoryStore:
    def __init__(self, database_path: str | Path | None = None) -> None:
        self.database_path = Path(database_path) if database_path else default_database_path()
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS resale_items (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    identifiers TEXT NOT NULL DEFAULT '{}',
                    source_refs TEXT NOT NULL DEFAULT '[]',
                    photo_refs TEXT NOT NULL DEFAULT '[]',
                    research_confidence REAL NOT NULL DEFAULT 0,
                    price_low REAL NOT NULL DEFAULT 0,
                    price_high REAL NOT NULL DEFAULT 0,
                    target_price REAL NOT NULL DEFAULT 0,
                    expected_effort_minutes INTEGER NOT NULL DEFAULT 15,
                    platform TEXT,
                    next_action TEXT,
                    notes TEXT NOT NULL DEFAULT '',
                    acquired_at TEXT,
                    posted_at TEXT,
                    sold_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_resale_status_priority
                    ON resale_items(status, priority, updated_at);
                CREATE INDEX IF NOT EXISTS idx_resale_sold_at
                    ON resale_items(sold_at);

                CREATE TABLE IF NOT EXISTS resale_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(item_id) REFERENCES resale_items(id) ON DELETE CASCADE
                );
                """
            )

    @staticmethod
    def _encode_item(item: Item) -> dict:
        data = item.to_dict()
        data.pop("expected_value", None)
        data["status"] = item.status.value
        data["priority"] = item.priority.value
        for name in JSON_FIELDS:
            data[name] = json.dumps(data[name], ensure_ascii=False, sort_keys=True)
        return data

    @staticmethod
    def _decode_row(row: sqlite3.Row) -> Item:
        data = dict(row)
        for name in JSON_FIELDS:
            try:
                data[name] = json.loads(data[name])
            except (TypeError, json.JSONDecodeError):
                data[name] = {} if name == "identifiers" else []
        data["status"] = ItemStatus(data["status"])
        data["priority"] = Priority(data["priority"])
        return Item(**data)

    def save(self, item: Item, *, event_type: str = "item.saved") -> Item:
        item.touch()
        data = self._encode_item(item)
        columns = [field.name for field in fields(Item)]
        placeholders = ", ".join(f":{column}" for column in columns)
        updates = ", ".join(f"{column}=excluded.{column}" for column in columns if column != "id")
        with self._connect() as connection:
            connection.execute(
                f"""
                INSERT INTO resale_items ({', '.join(columns)})
                VALUES ({placeholders})
                ON CONFLICT(id) DO UPDATE SET {updates}
                """,
                data,
            )
            connection.execute(
                "INSERT INTO resale_events(item_id, event_type, payload, created_at) VALUES (?, ?, ?, ?)",
                (item.id, event_type, json.dumps({"status": item.status.value}), utc_now()),
            )
        return item

    def get(self, item_id: str) -> Item | None:
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM resale_items WHERE id = ?", (item_id,)).fetchone()
        return self._decode_row(row) if row else None

    def list_items(self, statuses: Iterable[ItemStatus] | None = None) -> list[Item]:
        query = "SELECT * FROM resale_items"
        parameters: list[str] = []
        if statuses:
            values = [ItemStatus(status).value for status in statuses]
            query += f" WHERE status IN ({', '.join('?' for _ in values)})"
            parameters.extend(values)
        query += " ORDER BY updated_at DESC, id ASC"
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._decode_row(row) for row in rows]

    def transition(
        self,
        item_id: str,
        status: ItemStatus,
        *,
        platform: str | None = None,
        note: str | None = None,
    ) -> Item:
        item = self.get(item_id)
        if item is None:
            raise KeyError(f"unknown resale item: {item_id}")
        previous_status = item.status
        item.status = ItemStatus(status)
        if platform is not None:
            item.platform = platform.strip() or None
        if note:
            item.notes = f"{item.notes}\n{note}".strip()
        timestamp = utc_now()
        if item.status is ItemStatus.POSTED and not item.posted_at:
            item.posted_at = timestamp
        if item.status is ItemStatus.SOLD and not item.sold_at:
            item.sold_at = timestamp
        return self.save(item, event_type=f"status.{previous_status.value.lower()}_to_{item.status.value.lower()}")

    def delete(self, item_id: str) -> bool:
        with self._connect() as connection:
            cursor = connection.execute("DELETE FROM resale_items WHERE id = ?", (item_id,))
        return cursor.rowcount > 0

    def summary(self, now: datetime | None = None) -> dict:
        now = now or datetime.now(UTC)
        items = self.list_items()
        sold = [item for item in items if item.status is ItemStatus.SOLD and item.sold_at]

        def sold_since(delta: timedelta) -> list[Item]:
            threshold = now - delta
            result = []
            for item in sold:
                try:
                    sold_at = datetime.fromisoformat(item.sold_at or "")
                    if sold_at.tzinfo is None:
                        sold_at = sold_at.replace(tzinfo=UTC)
                    if sold_at >= threshold:
                        result.append(item)
                except ValueError:
                    continue
            return result

        def total_value(group: Iterable[Item]) -> float:
            return round(sum(item.target_price for item in group), 2)

        sale_days = []
        for item in sold:
            try:
                start = datetime.fromisoformat(item.posted_at or item.created_at)
                end = datetime.fromisoformat(item.sold_at or "")
                if start.tzinfo is None:
                    start = start.replace(tzinfo=UTC)
                if end.tzinfo is None:
                    end = end.replace(tzinfo=UTC)
                sale_days.append(max((end - start).total_seconds() / 86400, 0.0))
            except ValueError:
                continue

        counts = {status.value: 0 for status in ItemStatus}
        for item in items:
            counts[item.status.value] += 1

        return {
            "total_items": len(items),
            "status_counts": counts,
            "active_value": round(sum(item.expected_value for item in items if item.status not in {ItemStatus.SOLD, ItemStatus.HOLD}), 2),
            "sold_day": total_value(sold_since(timedelta(days=1))),
            "sold_week": total_value(sold_since(timedelta(days=7))),
            "sold_month": total_value(sold_since(timedelta(days=30))),
            "average_sale_days": round(sum(sale_days) / len(sale_days), 2) if sale_days else None,
        }

    def export_json(self) -> str:
        return json.dumps([item.to_dict() for item in self.list_items()], indent=2, ensure_ascii=False)

    def import_json(self, payload: str, *, preview: bool = False) -> list[Item]:
        data = json.loads(payload)
        if not isinstance(data, list):
            raise ValueError("inventory JSON must contain a list")
        items = [Item.from_dict(entry) for entry in data]
        if not preview:
            for item in items:
                self.save(item, event_type="item.imported")
        return items

    def export_csv(self) -> str:
        output = io.StringIO()
        fieldnames = [field.name for field in fields(Item)]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for item in self.list_items():
            row = self._encode_item(item)
            writer.writerow({name: row.get(name) for name in fieldnames})
        return output.getvalue()
