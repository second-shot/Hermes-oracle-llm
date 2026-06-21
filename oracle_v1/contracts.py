from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from typing import Any


class OracleHeatLevel(str, Enum):
    COLD_CONTROL = "cold_control"
    WARM_ACTIVE = "warm_active"
    PASTEL_CONFIRM = "pastel_confirm"
    BURNING_URGENT = "burning_urgent"
    LIQUID_GOLD_SUCCESS = "liquid_gold_success"


def _serialize(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {key: _serialize(item) for key, item in asdict(value).items()}
    if isinstance(value, list):
        return [_serialize(item) for item in value]
    if isinstance(value, dict):
        return {key: _serialize(item) for key, item in value.items()}
    return value


@dataclass(slots=True)
class UploadRecord:
    id: str
    name: str
    status: str
    created_at: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass(slots=True)
class ArchitectIntent:
    id: str
    label: str
    confidence: float
    rationale: str
    objective: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass(slots=True)
class NextAction:
    id: str
    kind: str
    title: str
    summary: str
    requires_confirmation: bool
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass(slots=True)
class OracleEvent:
    id: str
    kind: str
    summary: str
    created_at: str
    mode: str
    risk_level: str
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass(slots=True)
class ConfirmationRequest:
    id: str
    event_id: str
    action_label: str
    reason: str
    risk_level: str
    status: str
    created_at: str
    decided_at: str | None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass(slots=True)
class Notification:
    id: str
    kind: str
    title: str
    message: str
    level: str
    created_at: str
    read: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _serialize(self)


@dataclass(slots=True)
class OracleState:
    visual_state: str
    heat_level: OracleHeatLevel
    urgency: str
    requires_confirmation: bool
    next_best_action: NextAction
    last_event_summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "visualState": self.visual_state,
            "heatLevel": self.heat_level.value,
            "urgency": self.urgency,
            "requiresConfirmation": self.requires_confirmation,
            "nextBestAction": self.next_best_action.to_dict(),
            "lastEventSummary": self.last_event_summary,
        }

