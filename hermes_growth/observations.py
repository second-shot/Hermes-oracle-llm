from __future__ import annotations

from pathlib import Path

from hermes_growth.contracts import GrowthObservation
from hermes_growth.skill_registry import default_growth_root
from hermes_growth.storage import append_jsonl, read_jsonl


class ObservationStore:
    """Append-only local audit history with a deduplicated analysis view."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_growth_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "observations.jsonl"

    def append(self, observation: GrowthObservation) -> None:
        errors = observation.validate()
        if errors:
            raise ValueError("; ".join(errors))
        append_jsonl(self.path, observation.to_dict())

    def history(self) -> list[GrowthObservation]:
        return [
            GrowthObservation.from_dict(value)
            for value in read_jsonl(self.path)
        ]

    def observations(self) -> list[GrowthObservation]:
        unique: dict[str, GrowthObservation] = {}
        for observation in self.history():
            unique.setdefault(observation.observation_id, observation)
        return list(unique.values())
