from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hermes_growth.contracts import RiskClass, SkillManifest, SkillStatus


ALLOWED_TRANSITIONS: dict[SkillStatus, set[SkillStatus]] = {
    SkillStatus.OBSERVED: {SkillStatus.PROPOSED, SkillStatus.REJECTED},
    SkillStatus.PROPOSED: {SkillStatus.DRAFT, SkillStatus.REJECTED},
    SkillStatus.DRAFT: {SkillStatus.TESTED, SkillStatus.REJECTED},
    SkillStatus.TESTED: {SkillStatus.SHADOW, SkillStatus.REJECTED, SkillStatus.QUARANTINED},
    SkillStatus.SHADOW: {SkillStatus.CANARY, SkillStatus.REJECTED, SkillStatus.QUARANTINED},
    SkillStatus.CANARY: {SkillStatus.ACTIVE, SkillStatus.REJECTED, SkillStatus.QUARANTINED},
    SkillStatus.ACTIVE: {SkillStatus.QUARANTINED, SkillStatus.ROLLED_BACK},
    SkillStatus.QUARANTINED: {SkillStatus.ROLLED_BACK, SkillStatus.REJECTED},
    SkillStatus.REJECTED: set(),
    SkillStatus.ROLLED_BACK: set(),
}


def default_growth_root() -> Path:
    configured = os.environ.get("HERMES_DATA_DIR")
    if configured:
        return Path(configured) / "growth"
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        return Path(local_app_data) / "Hermes" / "growth"
    return Path.home() / ".hermes" / "growth"


class SkillRegistry:
    """Versioned local registry with explicit lifecycle and immutable audit events."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root is not None else default_growth_root()
        self.root.mkdir(parents=True, exist_ok=True)
        self.registry_path = self.root / "skill_registry.json"
        self.audit_path = self.root / "promotions.jsonl"
        if not self.registry_path.exists():
            self._write({"schema_version": 1, "skills": {}, "active": {}})

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"invalid skill registry: {exc}") from exc
        if value.get("schema_version") != 1:
            raise RuntimeError("unsupported skill registry schema")
        return value

    def _write(self, value: dict[str, Any]) -> None:
        temporary = self.registry_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.registry_path)

    def _audit(self, event: str, manifest: SkillManifest, **details: Any) -> None:
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event": event,
            "skill_id": manifest.skill_id,
            "version": manifest.version,
            "status": manifest.status.value,
            **details,
        }
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    def register(self, manifest: SkillManifest) -> SkillManifest:
        errors = manifest.validate()
        if errors:
            raise ValueError("; ".join(errors))
        value = self._read()
        versions = value["skills"].setdefault(manifest.skill_id, {})
        if manifest.version in versions:
            raise ValueError(f"skill version already exists: {manifest.skill_id}@{manifest.version}")
        versions[manifest.version] = manifest.to_dict()
        self._write(value)
        self._audit("registered", manifest)
        return manifest

    def get(self, skill_id: str, version: str) -> SkillManifest:
        value = self._read()
        try:
            payload = value["skills"][skill_id][version]
        except KeyError as exc:
            raise KeyError(f"unknown skill version: {skill_id}@{version}") from exc
        return SkillManifest.from_dict(payload)

    def active(self, skill_id: str) -> SkillManifest | None:
        value = self._read()
        version = value["active"].get(skill_id)
        return self.get(skill_id, version) if version else None

    def list_manifests(self) -> list[SkillManifest]:
        value = self._read()
        manifests = [
            SkillManifest.from_dict(payload)
            for versions in value["skills"].values()
            for payload in versions.values()
        ]
        return sorted(manifests, key=lambda item: (item.skill_id, item.version))

    def transition(
        self,
        skill_id: str,
        version: str,
        target: SkillStatus,
        *,
        approved: bool = False,
        evidence: str = "",
    ) -> SkillManifest:
        current = self.get(skill_id, version)
        if target not in ALLOWED_TRANSITIONS[current.status]:
            raise ValueError(f"invalid transition: {current.status.value} -> {target.value}")

        privileged = current.risk_class in {
            RiskClass.EXTERNAL,
            RiskClass.DESTRUCTIVE,
            RiskClass.PRIVILEGED,
        }
        if target == SkillStatus.ACTIVE and (privileged or current.approval_required) and not approved:
            raise PermissionError("explicit approval is required for this activation")
        if target in {SkillStatus.TESTED, SkillStatus.SHADOW, SkillStatus.CANARY, SkillStatus.ACTIVE} and not evidence.strip():
            raise ValueError("evaluation evidence is required")

        value = self._read()
        payload = dict(value["skills"][skill_id][version])
        previous_active = value["active"].get(skill_id)
        payload["status"] = target.value
        if target == SkillStatus.ACTIVE:
            if previous_active is None:
                raise ValueError("first activation requires a registered rollback baseline")
            if previous_active == version:
                raise ValueError("skill version is already active")
            payload["rollback_version"] = previous_active
            value["active"][skill_id] = version
        manifest = SkillManifest.from_dict(payload)
        value["skills"][skill_id][version] = manifest.to_dict()
        self._write(value)
        self._audit(
            "transitioned",
            manifest,
            from_status=current.status.value,
            approved=approved,
            evidence=evidence,
            previous_active=previous_active,
        )
        return manifest

    def set_baseline(self, skill_id: str, version: str, *, approved: bool) -> SkillManifest:
        if not approved:
            raise PermissionError("explicit approval is required to set the initial baseline")
        manifest = self.get(skill_id, version)
        if manifest.status != SkillStatus.ACTIVE:
            raise ValueError(
                "initial baseline manifest must already be ACTIVE with tests, evaluation evidence, and rollback target"
            )
        value = self._read()
        value["active"][skill_id] = version
        self._write(value)
        self._audit("baseline_set", manifest, approved=True)
        return manifest

    def quarantine(self, skill_id: str, version: str, reason: str) -> SkillManifest:
        if not reason.strip():
            raise ValueError("quarantine reason is required")
        return self.transition(
            skill_id,
            version,
            SkillStatus.QUARANTINED,
            evidence=reason,
        )

    def rollback(self, skill_id: str, version: str, *, approved: bool = False) -> SkillManifest:
        current = self.get(skill_id, version)
        if current.status not in {SkillStatus.ACTIVE, SkillStatus.QUARANTINED}:
            raise ValueError("only active or quarantined skills can be rolled back")
        if current.risk_class in {RiskClass.EXTERNAL, RiskClass.DESTRUCTIVE, RiskClass.PRIVILEGED} and not approved:
            raise PermissionError("explicit approval is required for privileged rollback")
        if not current.rollback_version:
            raise ValueError("no rollback target is recorded")

        value = self._read()
        target = self.get(skill_id, current.rollback_version)
        value["active"][skill_id] = target.version
        current_payload = current.to_dict()
        current_payload["status"] = SkillStatus.ROLLED_BACK.value
        value["skills"][skill_id][version] = current_payload
        self._write(value)
        rolled_back = SkillManifest.from_dict(current_payload)
        self._audit("rolled_back", rolled_back, restored_version=target.version, approved=approved)
        return target
