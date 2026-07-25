from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from resale.models import Item, ItemStatus, Priority
from resale.queue import build_daily_queue, score_item
from resale.store import InventoryStore


def test_item_normalizes_fields_and_expected_value() -> None:
    item = Item(
        title="  Blue Note LP  ",
        category=" Vinyl ",
        price_low=20,
        price_high=40,
        research_confidence=2,
    )

    assert item.title == "Blue Note LP"
    assert item.category == "vinyl"
    assert item.research_confidence == 1.0
    assert item.expected_value == 30


def test_inventory_store_persists_and_transitions(tmp_path) -> None:
    store = InventoryStore(tmp_path / "inventory.sqlite3")
    item = Item(title="Test record", target_price=35, priority=Priority.HIGH)

    store.save(item)
    posted = store.transition(item.id, ItemStatus.POSTED, platform="eBay")
    sold = store.transition(item.id, ItemStatus.SOLD)

    assert store.get(item.id) is not None
    assert posted.posted_at is not None
    assert sold.status is ItemStatus.SOLD
    assert sold.sold_at is not None
    assert sold.platform == "eBay"


def test_daily_queue_is_deterministic_and_excludes_hold_and_sold() -> None:
    now = datetime(2026, 7, 25, tzinfo=UTC)
    ready = Item(
        id="ready",
        title="Ready item",
        status=ItemStatus.READY,
        priority=Priority.HIGH,
        target_price=100,
        research_confidence=0.9,
        expected_effort_minutes=10,
        created_at=(now - timedelta(days=3)).isoformat(),
        updated_at=now.isoformat(),
    )
    research = Item(
        id="research",
        title="Research item",
        status=ItemStatus.RESEARCH,
        priority=Priority.MEDIUM,
        target_price=20,
        expected_effort_minutes=30,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )
    hold = Item(id="hold", title="Hold item", status=ItemStatus.HOLD, target_price=1000)
    sold = Item(id="sold", title="Sold item", status=ItemStatus.SOLD, target_price=1000)

    queue = build_daily_queue([research, hold, sold, ready], now=now)

    assert [entry.item_id for entry in queue] == ["ready", "research"]
    assert queue[0].action == "approve title, price and platform"
    assert score_item(ready, now) > score_item(research, now)


def test_json_import_preview_does_not_write(tmp_path) -> None:
    store = InventoryStore(tmp_path / "inventory.sqlite3")
    payload = json.dumps([Item(title="Preview item", target_price=50).to_dict()])

    preview = store.import_json(payload, preview=True)

    assert len(preview) == 1
    assert store.list_items() == []


def test_json_export_round_trip(tmp_path) -> None:
    first = InventoryStore(tmp_path / "first.sqlite3")
    first.save(Item(title="Magazine", category="magazine", target_price=15))
    first.save(Item(title="Bike frame", category="bike", status=ItemStatus.RESEARCH, price_low=40, price_high=90))

    payload = first.export_json()
    second = InventoryStore(tmp_path / "second.sqlite3")
    imported = second.import_json(payload)

    assert len(imported) == 2
    assert {item.title for item in second.list_items()} == {"Magazine", "Bike frame"}


def test_summary_reports_status_values_and_average_sale_time(tmp_path) -> None:
    store = InventoryStore(tmp_path / "inventory.sqlite3")
    now = datetime(2026, 7, 25, 12, 0, tzinfo=UTC)
    sold = Item(
        title="Sold record",
        status=ItemStatus.SOLD,
        target_price=45,
        posted_at=(now - timedelta(days=4)).isoformat(),
        sold_at=(now - timedelta(days=1)).isoformat(),
    )
    ready = Item(title="Ready record", status=ItemStatus.READY, target_price=25)
    store.save(sold)
    store.save(ready)

    summary = store.summary(now=now)

    assert summary["status_counts"]["SOLD"] == 1
    assert summary["status_counts"]["READY"] == 1
    assert summary["sold_week"] == 45
    assert summary["average_sale_days"] == 3
    assert summary["active_value"] == 25
