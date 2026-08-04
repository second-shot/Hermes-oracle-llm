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
