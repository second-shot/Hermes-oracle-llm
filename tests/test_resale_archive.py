from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from hermes_modules.resale_archive import ResaleArchive


class ResaleArchiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.archive = ResaleArchive(self.root / "archive.sqlite3")

    def tearDown(self) -> None:
        self.archive.close()
        self.temp.cleanup()

    def item(self, title: str, **overrides):
        return {
            "title": title,
            "category": "vinyl",
            "provenance": "manual capture",
            "target_price": 25,
            "research_confidence": 0.8,
            **overrides,
        }

    def test_safe_initialization_and_status_action(self) -> None:
        item_id = self.archive.capture(self.item("Test pressing"))
        changed = self.archive.apply_action(item_id, "approve")
        self.assertEqual(changed["status"], "READY")
        self.assertTrue(self.archive.database.is_file())

    def test_queue_is_deterministic_and_value_aware(self) -> None:
        low = self.archive.capture(self.item("Low", target_price=10, priority=0))
        high = self.archive.capture(
            self.item("High", target_price=100, priority=2, status="READY")
        )
        first = [item["id"] for item in self.archive.daily_queue()]
        second = [item["id"] for item in self.archive.daily_queue()]
        self.assertEqual(first, second)
        self.assertEqual(first, [high, low])

    def test_json_round_trip(self) -> None:
        self.archive.capture(
            self.item(
                "Round trip",
                photo_refs=["photo:1"],
                identifiers={"catalogue": "ABC-1"},
            )
        )
        export = self.archive.export_json(self.root / "items.json")
        target = ResaleArchive(self.root / "target.sqlite3")
        try:
            target.import_json(export)
            self.assertEqual(target.items()[0]["identifiers"]["catalogue"], "ABC-1")
        finally:
            target.close()

    def test_dispatch_records_sale_without_external_action(self) -> None:
        item_id = self.archive.capture(self.item("Sold"))
        item = self.archive.apply_action(item_id, "dispatch", sold_price=30)
        self.assertEqual(item["status"], "SOLD")
        self.assertEqual(self.archive.summary(1)["revenue"], 30)

    def test_invalid_status_rejected(self) -> None:
        with self.assertRaises(ValueError):
            self.archive.capture(self.item("Bad", status="AUTO_POST"))


if __name__ == "__main__":
    unittest.main()
