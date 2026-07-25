from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable

from resale.models import Item, ItemStatus, Priority


STATUS_WEIGHT = {
    ItemStatus.READY: 100,
    ItemStatus.RESEARCH: 80,
    ItemStatus.FIX: 65,
    ItemStatus.CAPTURED: 55,
    ItemStatus.POSTED: 35,
    ItemStatus.HOLD: 5,
    ItemStatus.SOLD: 0,
}

PRIORITY_WEIGHT = {
    Priority.HIGH: 30,
    Priority.MEDIUM: 15,
    Priority.LOW: 0,
}

DEFAULT_ACTION = {
    ItemStatus.CAPTURED: "identify, photograph and price",
    ItemStatus.RESEARCH: "confirm an exact match and sold value",
    ItemStatus.READY: "approve title, price and platform",
    ItemStatus.POSTED: "monitor offers and prepare dispatch",
    ItemStatus.SOLD: "pack, send and record the result",
    ItemStatus.HOLD: "wait for stronger evidence or timing",
    ItemStatus.FIX: "clean, repair or retake photographs",
}


@dataclass(frozen=True, slots=True)
class QueueEntry:
    item_id: str
    title: str
    status: str
    priority: str
    action: str
    expected_value: float
    expected_effort_minutes: int
    score: float


def _age_days(item: Item, now: datetime) -> float:
    try:
        created = datetime.fromisoformat(item.created_at)
        if created.tzinfo is None:
            created = created.replace(tzinfo=UTC)
        return max((now - created).total_seconds() / 86400, 0.0)
    except (TypeError, ValueError):
        return 0.0


def score_item(item: Item, now: datetime | None = None) -> float:
    now = now or datetime.now(UTC)
    value_score = min(item.expected_value, 500.0) / 10.0
    confidence_score = item.research_confidence * 20.0
    effort_penalty = min(item.expected_effort_minutes, 240) / 12.0
    age_score = min(_age_days(item, now), 30.0)
    return round(
        STATUS_WEIGHT[item.status]
        + PRIORITY_WEIGHT[item.priority]
        + value_score
        + confidence_score
        + age_score
        - effort_penalty,
        3,
    )


def build_daily_queue(
    items: Iterable[Item],
    *,
    limit: int = 20,
    include_posted: bool = True,
    now: datetime | None = None,
) -> list[QueueEntry]:
    eligible = []
    for item in items:
        if item.status in {ItemStatus.SOLD, ItemStatus.HOLD}:
            continue
        if item.status is ItemStatus.POSTED and not include_posted:
            continue
        eligible.append(item)

    ranked = sorted(
        eligible,
        key=lambda item: (-score_item(item, now), item.updated_at, item.id),
    )
    return [
        QueueEntry(
            item_id=item.id,
            title=item.title,
            status=item.status.value,
            priority=item.priority.value,
            action=item.next_action or DEFAULT_ACTION[item.status],
            expected_value=round(item.expected_value, 2),
            expected_effort_minutes=item.expected_effort_minutes,
            score=score_item(item, now),
        )
        for item in ranked[: max(limit, 0)]
    ]
