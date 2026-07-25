from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class ItemStatus(StrEnum):
    CAPTURED = "CAPTURED"
    RESEARCH = "RESEARCH"
    READY = "READY"
    POSTED = "POSTED"
    SOLD = "SOLD"
    HOLD = "HOLD"
    FIX = "FIX"


class Priority(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class Item:
    title: str
    category: str = "other"
    id: str = field(default_factory=lambda: str(uuid4()))
    status: ItemStatus = ItemStatus.CAPTURED
    priority: Priority = Priority.MEDIUM
    condition: str = "unknown"
    identifiers: dict[str, str] = field(default_factory=dict)
    source_refs: list[str] = field(default_factory=list)
    photo_refs: list[str] = field(default_factory=list)
    research_confidence: float = 0.0
    price_low: float = 0.0
    price_high: float = 0.0
    target_price: float = 0.0
    expected_effort_minutes: int = 15
    platform: str | None = None
    next_action: str | None = None
    notes: str = ""
    acquired_at: str | None = None
    posted_at: str | None = None
    sold_at: str | None = None
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    def __post_init__(self) -> None:
        self.title = self.title.strip()
        self.category = self.category.strip().lower() or "other"
        self.condition = self.condition.strip().lower() or "unknown"
        self.research_confidence = min(max(float(self.research_confidence), 0.0), 1.0)
        self.price_low = max(float(self.price_low), 0.0)
        self.price_high = max(float(self.price_high), self.price_low)
        self.target_price = max(float(self.target_price), 0.0)
        self.expected_effort_minutes = max(int(self.expected_effort_minutes), 1)
        if not self.title:
            raise ValueError("item title is required")

    @property
    def expected_value(self) -> float:
        if self.target_price > 0:
            return self.target_price
        if self.price_high > 0:
            return (self.price_low + self.price_high) / 2
        return self.price_low

    def touch(self) -> None:
        self.updated_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["priority"] = self.priority.value
        data["expected_value"] = self.expected_value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Item":
        payload = dict(data)
        payload.pop("expected_value", None)
        payload["status"] = ItemStatus(payload.get("status", ItemStatus.CAPTURED))
        payload["priority"] = Priority(payload.get("priority", Priority.MEDIUM))
        return cls(**payload)
