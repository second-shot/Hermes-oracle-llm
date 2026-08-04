from __future__ import annotations

import json

import pytest

from hermes_growth.contracts import RiskClass, SkillManifest, SkillStatus
from hermes_growth.skill_registry import SkillRegistry


def manifest(
    version: str,
    *,
    status: SkillStatus = SkillStatus.DRAFT,
    risk: RiskClass = RiskClass.SAFE,
    approval_required: bool = False,
) -> SkillManifest:
    return SkillManifest(
        skill_id="resale-research",
        version=version,
        purpose="Research and structure resale evidence",
        domain="resale",
        input_schema={"type": "object"},
        output_schema={"type": "object"},
        risk_class=risk,
        status=status,
        test_paths=["tests/test_resale_research.py"] if status != SkillStatus.DRAFT else [],
        evaluation_paths=["evaluations/resale-research.json"]
        if status in {SkillStatus.SHADOW, SkillStatus.CANARY, SkillStatus.ACTIVE}
        else [],
        approval_required=approval_required,
        rollback_version=version if status == SkillStatus.ACTIVE else None,
    )


def test_privileged_manifest_requires_approval_gate() -> None:
    candidate = manifest("1.0.0", risk=RiskClass.EXTERNAL)
    assert "EXTERNAL skills must require approval" in candidate.validate()


def test_registry_rejects_duplicate_versions(tmp_path) -> None:
    registry = SkillRegistry(tmp_path)
    registry.register(manifest("1.0.0"))
    with pytest.raises(ValueError, match="already exists"):
        registry.register(manifest("1.0.0"))


def test_lifecycle_requires_evidence_and_preserves_rollback(tmp_path) -> None:
    registry = SkillRegistry(tmp_path)
    registry.register(manifest("1.0.0"))
    baseline = registry.set_baseline("resale-research", "1.0.0", approved=True)
    assert baseline.status == SkillStatus.ACTIVE

    registry.register(manifest("1.1.0"))
    with pytest.raises(ValueError, match="evaluation evidence"):
        registry.transition("resale-research", "1.1.0", SkillStatus.TESTED)

    tested = registry.transition(
        "resale-research", "1.1.0", SkillStatus.TESTED, evidence="12 focused tests passed"
    )
    assert tested.status == SkillStatus.TESTED

    shadow = registry.transition(
        "resale-research", "1.1.0", SkillStatus.SHADOW, evidence="20 shadow comparisons passed"
    )
    assert shadow.status == SkillStatus.SHADOW

    canary = registry.transition(
        "resale-research", "1.1.0", SkillStatus.CANARY, evidence="10 reversible canary tasks passed"
    )
    assert canary.status == SkillStatus.CANARY

    active = registry.transition(
        "resale-research", "1.1.0", SkillStatus.ACTIVE, evidence="quality improved by 18%"
    )
    assert active.status == SkillStatus.ACTIVE
    assert active.rollback_version == "1.0.0"
    assert registry.active("resale-research").version == "1.1.0"

    registry.quarantine("resale-research", "1.1.0", "regression rate exceeded baseline")
    restored = registry.rollback("resale-research", "1.1.0")
    assert restored.version == "1.0.0"
    assert registry.active("resale-research").version == "1.0.0"


def test_external_activation_requires_explicit_approval(tmp_path) -> None:
    registry = SkillRegistry(tmp_path)
    registry.register(manifest("1.0.0"))
    registry.set_baseline("resale-research", "1.0.0", approved=True)

    candidate = manifest(
        "2.0.0", risk=RiskClass.EXTERNAL, approval_required=True
    )
    registry.register(candidate)
    registry.transition("resale-research", "2.0.0", SkillStatus.TESTED, evidence="tests passed")
    registry.transition("resale-research", "2.0.0", SkillStatus.SHADOW, evidence="shadow passed")
    registry.transition("resale-research", "2.0.0", SkillStatus.CANARY, evidence="canary passed")

    with pytest.raises(PermissionError, match="explicit approval"):
        registry.transition(
            "resale-research", "2.0.0", SkillStatus.ACTIVE, evidence="evaluation passed"
        )

    active = registry.transition(
        "resale-research",
        "2.0.0",
        SkillStatus.ACTIVE,
        approved=True,
        evidence="operator approved evaluation report",
    )
    assert active.status == SkillStatus.ACTIVE


def test_audit_log_is_append_only_jsonl(tmp_path) -> None:
    registry = SkillRegistry(tmp_path)
    registry.register(manifest("1.0.0"))
    registry.set_baseline("resale-research", "1.0.0", approved=True)

    records = [json.loads(line) for line in registry.audit_path.read_text(encoding="utf-8").splitlines()]
    assert [record["event"] for record in records] == ["registered", "baseline_set"]
    assert all(record["skill_id"] == "resale-research" for record in records)
