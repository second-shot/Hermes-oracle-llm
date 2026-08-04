from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class SkillStatus(StrEnum):
    OBSERVED = "OBSERVED"
    PROPOSED = "PROPOSED"
    DRAFT = "DRAFT"
    TESTED = "TESTED"
    SHADOW = "SHADOW"
    CANARY = "CANARY"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    QUARANTINED = "QUARANTINED"
    ROLLED_BACK = "ROLLED_BACK"


class RiskClass(StrEnum):
    SAFE = "SAFE"
    REVERSIBLE = "REVERSIBLE"
    EXTERNAL = "EXTERNAL"
    DESTRUCTIVE = "DESTRUCTIVE"
    PRIVILEGED = "PRIVILEGED"


class ObservationKind(StrEnum):
    COMPLETION = "completion"
    FAILURE = "failure"
    RETRY = "retry"
    MISSING_SKILL = "missing_skill"
    OPERATOR_CORRECTION = "operator_correction"
    INEFFICIENT_WORKAROUND = "inefficient_workaround"
    LOW_CONFIDENCE = "low_confidence"
    BUDGET_EXCESS = "budget_excess"
    MODULE_CONFLICT = "duplicate_conflicting_modules"
    STRUCTURAL_REGRESSION = "structural_regression"


class RecommendedResponse(StrEnum):
    NEW_SKILL = "new_skill"
    IMPROVE_SKILL = "improve_skill"
    ROUTER_ADJUSTMENT = "router_adjustment"
    DOCUMENTATION = "documentation"
    STRUCTURAL_REPAIR = "structural_repair"
    NO_CHANGE = "no_change"


class FeedbackStatus(StrEnum):
    ACCEPTED = "accepted"
    CORRECTED = "corrected"
    REJECTED = "rejected"
    PARTIALLY_USEFUL = "partially_useful"
    SUPERSEDED = "superseded"


class FeedbackScope(StrEnum):
    TASK = "task"
    PROJECT = "project"
    GLOBAL = "global"


@dataclass(slots=True)
class GrowthObservation:
    observation_id: str
    timestamp: str
    project_id: str
    task_id: str
    task_class: str
    kind: ObservationKind
    skill_id: str
    skill_version: str
    expected_outcome: str
    actual_outcome: str
    success: bool
    confidence: float
    retry_count: int
    latency_ms: int
    operator_correction: str
    evidence: list[str]
    affected_modules: list[str]
    risk_class: RiskClass
    provenance: list[str]

    def validate(self) -> list[str]:
        errors: list[str] = []
        for field_name in (
            "observation_id", "timestamp", "project_id", "task_id", "task_class",
            "skill_id", "skill_version", "expected_outcome", "actual_outcome",
        ):
            if not str(getattr(self, field_name)).strip():
                errors.append(f"{field_name} is required")
        if not 0.0 <= self.confidence <= 1.0:
            errors.append("confidence must be between 0 and 1")
        if self.retry_count < 0:
            errors.append("retry_count cannot be negative")
        if self.latency_ms < 0:
            errors.append("latency_ms cannot be negative")
        if not any(item.strip() for item in self.evidence):
            errors.append("evidence is required")
        if not self.affected_modules or not any(item.strip() for item in self.affected_modules):
            errors.append("affected_modules is required")
        if not any(item.strip() for item in self.provenance):
            errors.append("provenance is required")
        return errors

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["kind"] = self.kind.value
        value["risk_class"] = self.risk_class.value
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GrowthObservation":
        payload = dict(value)
        payload["kind"] = ObservationKind(payload["kind"])
        payload["risk_class"] = RiskClass(payload["risk_class"])
        observation = cls(**payload)
        errors = observation.validate()
        if errors:
            raise ValueError("; ".join(errors))
        return observation


@dataclass(slots=True)
class GapCandidate:
    gap_id: str
    task_cluster: str
    domain_cluster: str
    supporting_observation_ids: list[str]
    frequency: int
    severity: str
    expected_value: str
    confidence: float
    skills_considered: list[str]
    justification: str
    evidence: list[str]
    recommended_response: RecommendedResponse
    status: str = "open"

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["recommended_response"] = self.recommended_response.value
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GapCandidate":
        payload = dict(value)
        payload["recommended_response"] = RecommendedResponse(payload["recommended_response"])
        return cls(**payload)


@dataclass(slots=True)
class Reflection:
    reflection_id: str
    timestamp: str
    project_id: str
    task_id: str
    intended_result: str
    actual_result: str
    evidence_references: list[str]
    worked: list[str]
    failed: list[str]
    disproved_assumptions: list[str]
    corrections: list[str]
    reusable_lessons: list[str]
    change_type: RecommendedResponse
    next_checkpoint: str

    def validate(self) -> list[str]:
        errors: list[str] = []
        for field_name in (
            "reflection_id", "timestamp", "project_id", "task_id", "intended_result",
            "actual_result", "next_checkpoint",
        ):
            if not str(getattr(self, field_name)).strip():
                errors.append(f"{field_name} is required")
        if not any(item.strip() for item in self.evidence_references):
            errors.append("evidence_references is required")
        return errors

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["change_type"] = self.change_type.value
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Reflection":
        payload = dict(value)
        payload["change_type"] = RecommendedResponse(payload["change_type"])
        reflection = cls(**payload)
        errors = reflection.validate()
        if errors:
            raise ValueError("; ".join(errors))
        return reflection


@dataclass(slots=True)
class GrowthFeedback:
    feedback_id: str
    timestamp: str
    status: FeedbackStatus
    contributor: str
    project_id: str
    task_id: str
    skill_id: str
    skill_version: str
    concrete_correction: str
    reason: str
    evidence: list[str]
    scope: FeedbackScope
    operator_approved: bool = False

    def validate(self) -> list[str]:
        errors: list[str] = []
        for field_name in (
            "feedback_id", "timestamp", "contributor", "project_id", "task_id",
            "skill_id", "skill_version", "concrete_correction", "reason",
        ):
            if not str(getattr(self, field_name)).strip():
                errors.append(f"{field_name} is required")
        if not any(item.strip() for item in self.evidence):
            errors.append("evidence is required")
        return errors

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["status"] = self.status.value
        value["scope"] = self.scope.value
        return value

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "GrowthFeedback":
        payload = dict(value)
        payload["status"] = FeedbackStatus(payload["status"])
        payload["scope"] = FeedbackScope(payload["scope"])
        feedback = cls(**payload)
        errors = feedback.validate()
        if errors:
            raise ValueError("; ".join(errors))
        return feedback


@dataclass(slots=True)
class SkillManifest:
    skill_id: str
    version: str
    purpose: str
    domain: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    risk_class: RiskClass = RiskClass.SAFE
    status: SkillStatus = SkillStatus.DRAFT
    tools: list[str] = field(default_factory=list)
    filesystem_scope: list[str] = field(default_factory=list)
    network_scope: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    test_paths: list[str] = field(default_factory=list)
    evaluation_paths: list[str] = field(default_factory=list)
    success_metrics: dict[str, float] = field(default_factory=dict)
    known_failure_modes: list[str] = field(default_factory=list)
    author: str = "human"
    provenance: list[str] = field(default_factory=list)
    approval_required: bool = False
    rollback_version: str | None = None

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.skill_id.strip():
            errors.append("skill_id is required")
        if not self.version.strip():
            errors.append("version is required")
        if not self.purpose.strip():
            errors.append("purpose is required")
        if not self.domain.strip():
            errors.append("domain is required")
        if not isinstance(self.input_schema, dict):
            errors.append("input_schema must be an object")
        if not isinstance(self.output_schema, dict):
            errors.append("output_schema must be an object")
        if self.status in {SkillStatus.TESTED, SkillStatus.SHADOW, SkillStatus.CANARY, SkillStatus.ACTIVE} and not self.test_paths:
            errors.append(f"{self.status.value} skills require test_paths")
        if self.status in {SkillStatus.SHADOW, SkillStatus.CANARY, SkillStatus.ACTIVE} and not self.evaluation_paths:
            errors.append(f"{self.status.value} skills require evaluation_paths")
        if self.risk_class in {RiskClass.EXTERNAL, RiskClass.DESTRUCTIVE, RiskClass.PRIVILEGED}:
            if not self.approval_required:
                errors.append(f"{self.risk_class.value} skills must require approval")
        if self.status == SkillStatus.ACTIVE and self.rollback_version is None:
            errors.append("ACTIVE skills require rollback_version")
        return errors

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["risk_class"] = self.risk_class.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "SkillManifest":
        payload = dict(value)
        payload["risk_class"] = RiskClass(payload.get("risk_class", RiskClass.SAFE))
        payload["status"] = SkillStatus(payload.get("status", SkillStatus.DRAFT))
        manifest = cls(**payload)
        errors = manifest.validate()
        if errors:
            raise ValueError("; ".join(errors))
        return manifest
