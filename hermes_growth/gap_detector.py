from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from pathlib import Path

from hermes_growth.contracts import (
    GapCandidate,
    GrowthObservation,
    ObservationKind,
    RecommendedResponse,
    RiskClass,
)
from hermes_growth.observations import ObservationStore
from hermes_growth.skill_registry import default_growth_root
from hermes_growth.storage import atomic_write_json, growth_lock


_DEFAULT_CLUSTER_WINDOW_DAYS = 30
_POLICY_PATH = Path(__file__).resolve().parents[1] / "policies" / "growth_policy.json"


def cluster_window_days() -> int:
    try:
        policy = json.loads(_POLICY_PATH.read_text(encoding="utf-8"))
        value = int(policy["gap_detection"]["cluster_window_days"])
        return value if value > 0 else _DEFAULT_CLUSTER_WINDOW_DAYS
    except (FileNotFoundError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        return _DEFAULT_CLUSTER_WINDOW_DAYS


def recent_observations(
    observations: list[GrowthObservation], *, now: datetime | None = None
) -> list[GrowthObservation]:
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    cutoff = current - timedelta(days=cluster_window_days())
    recent: list[GrowthObservation] = []
    for item in observations:
        try:
            timestamp = datetime.fromisoformat(item.timestamp)
        except ValueError:
            continue
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        if timestamp >= cutoff:
            recent.append(item)
    return recent


class GapDetector:
    """Derive stable, auditable candidates without generating skill implementations."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_growth_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "gap_candidates.json"

    def detect(self, observations: list[GrowthObservation] | None = None) -> list[GapCandidate]:
        with growth_lock(self.root):
            return self._detect_locked(observations)

    def _detect_locked(
        self, observations: list[GrowthObservation] | None = None
    ) -> list[GapCandidate]:
        source = observations if observations is not None else ObservationStore(self.root).observations()
        source = recent_observations(source)
        unique = {item.observation_id: item for item in source}.values()
        clusters: dict[str, list[GrowthObservation]] = defaultdict(list)
        for item in unique:
            if (
                not item.success
                or item.operator_correction
                or item.kind in {
                    ObservationKind.OPERATOR_CORRECTION,
                    ObservationKind.STRUCTURAL_REGRESSION,
                }
            ):
                clusters[item.task_class].append(item)

        candidates: list[GapCandidate] = []
        for cluster, items in sorted(clusters.items()):
            critical = [
                item for item in items
                if item.kind == ObservationKind.STRUCTURAL_REGRESSION
                and item.risk_class in {RiskClass.DESTRUCTIVE, RiskClass.PRIVILEGED}
            ]
            corrections = [
                item for item in items
                if item.operator_correction.strip() or item.kind == ObservationKind.OPERATOR_CORRECTION
            ]
            failures = [item for item in items if not item.success]
            if not critical and len(corrections) < 2 and len(failures) < 3:
                continue

            if critical:
                severity = "critical"
                response = RecommendedResponse.STRUCTURAL_REPAIR
                justification = "critical structural regression requires immediate repair"
            elif len(corrections) >= 2:
                severity = "high"
                response = RecommendedResponse.IMPROVE_SKILL
                justification = "repeated explicit operator corrections exceeded threshold"
            else:
                severity = "medium"
                missing_skill = all(item.kind == ObservationKind.MISSING_SKILL for item in failures)
                response = (
                    RecommendedResponse.NEW_SKILL
                    if missing_skill
                    else RecommendedResponse.IMPROVE_SKILL
                )
                justification = (
                    "repeated tasks lacked a suitable skill"
                    if missing_skill
                    else "related failures exceeded the default threshold"
                )

            support = items
            support_ids = sorted(item.observation_id for item in support)
            gap_id = "gap-" + hashlib.sha256(cluster.encode("utf-8")).hexdigest()[:12]
            skills = sorted({f"{item.skill_id}@{item.skill_version}" for item in support if item.skill_id})
            evidence = sorted({entry for item in support for entry in item.evidence})
            candidates.append(
                GapCandidate(
                    gap_id=gap_id,
                    task_cluster=cluster,
                    domain_cluster=cluster.split(".", 1)[0],
                    supporting_observation_ids=support_ids,
                    frequency=len(support_ids),
                    severity=severity,
                    expected_value="reduce repeated corrections and failed outcomes",
                    confidence=min(0.99, 0.55 + 0.1 * len(support_ids)),
                    skills_considered=skills,
                    justification=justification,
                    evidence=evidence,
                    recommended_response=response,
                )
            )

        self._write(candidates)
        return candidates

    def candidates(self) -> list[GapCandidate]:
        if not self.path.exists():
            return []
        value = json.loads(self.path.read_text(encoding="utf-8"))
        return [GapCandidate.from_dict(item) for item in value.get("candidates", [])]

    def _write(self, candidates: list[GapCandidate]) -> None:
        payload = {"schema_version": 1, "candidates": [item.to_dict() for item in candidates]}
        atomic_write_json(self.path, payload)
