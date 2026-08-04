from __future__ import annotations

from collections import Counter
from pathlib import Path

from hermes_growth.contracts import FeedbackScope, FeedbackStatus, GrowthFeedback
from hermes_growth.gap_detector import GapDetector
from hermes_growth.observations import ObservationStore
from hermes_growth.reflection import ReflectionStore
from hermes_growth.skill_registry import default_growth_root
from hermes_growth.storage import append_jsonl, growth_lock, read_jsonl


class FeedbackStore:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_growth_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "feedback.jsonl"

    def append(self, feedback: GrowthFeedback) -> None:
        errors = feedback.validate()
        if errors:
            raise ValueError("; ".join(errors))
        if feedback.scope == FeedbackScope.GLOBAL:
            if not feedback.operator_approved or not feedback.evidence:
                raise PermissionError("global feedback requires explicit operator approval and evidence")
        identity_fields = (
            "contributor", "project_id", "task_id", "skill_id", "skill_version", "scope"
        )
        with growth_lock(self.root):
            for existing in self.history():
                if existing.feedback_id != feedback.feedback_id:
                    continue
                if any(
                    getattr(existing, field_name) != getattr(feedback, field_name)
                    for field_name in identity_fields
                ):
                    raise ValueError("feedback identity fields are immutable")
            append_jsonl(self.path, feedback.to_dict())

    def history(self) -> list[GrowthFeedback]:
        return [
            GrowthFeedback.from_dict(value)
            for value in read_jsonl(self.path)
        ]

    def feedback(self) -> list[GrowthFeedback]:
        current: dict[str, GrowthFeedback] = {}
        for item in self.history():
            current[item.feedback_id] = item
        return list(current.values())


def growth_status(root: str | Path | None = None) -> dict[str, object]:
    growth_root = Path(root) if root is not None else default_growth_root()
    with growth_lock(growth_root):
        observations = ObservationStore(growth_root).observations()
        gaps = GapDetector(growth_root).detect(observations)
        reflections = ReflectionStore(growth_root).reflections()
        feedback = FeedbackStore(growth_root).feedback()
        failure_counts = Counter(item.task_class for item in observations if not item.success)
        unresolved = [
            item.feedback_id
            for item in feedback
            if item.status in {FeedbackStatus.CORRECTED, FeedbackStatus.PARTIALLY_USEFUL}
        ]
        next_checkpoint = (
            reflections[-1].next_checkpoint
            if reflections
            else (f"review gap {gaps[0].gap_id}" if gaps else "record the next meaningful task outcome")
        )
        return {
            "observation_count": len(observations),
            "repeated_failure_clusters": sorted(
                cluster for cluster, count in failure_counts.items() if count >= 3
            ),
            "open_gaps": [gap.to_dict() for gap in gaps if gap.status == "open"],
            "recent_reflections": [item.to_dict() for item in reflections[-5:]],
            "unresolved_corrections": unresolved,
            "next_recommended_checkpoint": next_checkpoint,
        }
