from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.services.provider_registry import DEFAULT_CONFIG_PATH, load_rotation_config


DEFAULT_MANIFEST_PATH = Path(__file__).resolve().parents[2] / "config" / "ecosystem.modules.json"


@dataclass(frozen=True)
class ModuleCheck:
    id: str
    name: str
    group: str
    declared_status: str
    health: str
    description: str
    entrypoint: str
    upkeep: str
    missing_files: tuple[str, ...]
    empty_files: tuple[str, ...]
    test_files: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "group": self.group,
            "declared_status": self.declared_status,
            "health": self.health,
            "description": self.description,
            "entrypoint": self.entrypoint,
            "upkeep": self.upkeep,
            "missing_files": list(self.missing_files),
            "empty_files": list(self.empty_files),
            "test_files": list(self.test_files),
        }


class EcosystemControlPlane:
    def __init__(
        self,
        project_root: str | Path | None = None,
        manifest_path: str | Path = DEFAULT_MANIFEST_PATH,
        rotation_path: str | Path = DEFAULT_CONFIG_PATH,
    ) -> None:
        self.project_root = (
            Path(project_root).resolve()
            if project_root is not None
            else Path(__file__).resolve().parents[2]
        )
        self.manifest_path = Path(manifest_path)
        self.rotation_path = Path(rotation_path)
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self.rotation = load_rotation_config(self.rotation_path)

    def modules(self) -> list[ModuleCheck]:
        checks: list[ModuleCheck] = []
        for module in self.manifest.get("modules", []):
            required = [str(value) for value in module.get("required_files", [])]
            missing = tuple(path for path in required if not (self.project_root / path).is_file())
            empty = tuple(
                path
                for path in required
                if (self.project_root / path).is_file() and (self.project_root / path).stat().st_size == 0
            )
            declared_status = str(module.get("status", "incubating"))
            if missing or empty:
                health = "attention"
            elif declared_status == "active":
                health = "healthy"
            elif declared_status == "locked":
                health = "locked"
            else:
                health = "building"
            checks.append(
                ModuleCheck(
                    id=str(module["id"]),
                    name=str(module["name"]),
                    group=str(module.get("group", "module")),
                    declared_status=declared_status,
                    health=health,
                    description=str(module.get("description", "")),
                    entrypoint=str(module.get("entrypoint", "")),
                    upkeep=str(module.get("upkeep", "Manual review")),
                    missing_files=missing,
                    empty_files=empty,
                    test_files=tuple(str(value) for value in module.get("test_files", [])),
                )
            )
        return checks

    def cost_posture(self) -> dict[str, Any]:
        providers = self.rotation.get("providers", {})
        local = []
        cloud = []
        for name, provider in providers.items():
            base_url = str(provider.get("base_url", "")).lower()
            is_cloud = base_url.startswith("https://")
            item = {
                "id": name,
                "enabled": bool(provider.get("enabled", False)),
                "priority": provider.get("priority"),
                "cost": provider.get("cost", "unknown"),
                "manual_unlock_only": bool(provider.get("manual_unlock_only", False)),
            }
            (cloud if is_cloud else local).append(item)

        safety = self.rotation.get("safety", {})
        cloud_unlock = self.rotation.get("cloud_unlock", {})
        return {
            "default_cost_usd": 0,
            "mode": self.rotation.get("hermes", {}).get("mode", "local_first"),
            "cloud_auto_fallback": bool(self.rotation.get("hermes", {}).get("cloud_auto_fallback", False)),
            "cloud_locked": not bool(cloud_unlock.get("enabled", False)),
            "paid_models_allowed": bool(cloud_unlock.get("paid_models_allowed", False)),
            "max_cloud_requests_per_day": int(safety.get("max_cloud_requests_per_day", 0)),
            "max_cloud_spend_per_day_usd": float(safety.get("max_cloud_spend_per_day_usd", 0)),
            "local_providers": sorted(local, key=lambda item: (item["priority"] or 999, item["id"])),
            "cloud_providers": sorted(cloud, key=lambda item: (item["priority"] or 999, item["id"])),
        }

    def rotation_matrix(self) -> list[dict[str, Any]]:
        models = self.rotation.get("models", {})
        rows = []
        for route_name, route in self.rotation.get("task_routes", {}).items():
            model_key = str(route.get("use_model", "fast_chat"))
            model = models.get(model_key, {})
            rows.append(
                {
                    "route": route_name,
                    "model_key": model_key,
                    "role": model.get("role", ""),
                    "candidates": model.get("model_candidates", []),
                    "max_tokens": model.get("params", {}).get("max_tokens"),
                    "requires_approval": bool(route.get("require_human_approval_before_write", False)),
                }
            )
        return rows

    def upkeep_report(self) -> dict[str, Any]:
        modules = self.modules()
        blockers = []
        warnings = []
        for module in modules:
            if module.declared_status == "active" and module.health == "attention":
                blockers.append(
                    {
                        "module": module.id,
                        "message": "Active module has missing or empty required files.",
                        "missing_files": list(module.missing_files),
                        "empty_files": list(module.empty_files),
                    }
                )
            elif module.health in {"building", "locked"}:
                warnings.append(
                    {
                        "module": module.id,
                        "message": (
                            "Module is intentionally locked."
                            if module.health == "locked"
                            else "Module remains incubating until its contracts and tests exist."
                        ),
                    }
                )

        empty_scaffolds = sorted(
            str(path.relative_to(self.project_root)).replace("\\", "/")
            for path in (self.project_root / "backend").rglob("*.py")
            if path.stat().st_size == 0
        )
        if empty_scaffolds:
            warnings.append(
                {
                    "module": "repository",
                    "message": "Empty backend scaffolds should be implemented or removed in a reviewed checkpoint.",
                    "files": empty_scaffolds,
                }
            )

        return {
            "status": "pass" if not blockers else "fail",
            "blockers": blockers,
            "warnings": warnings,
            "next_actions": [
                "Keep the Nous Hermes core upgradeable; extend through modules and skills.",
                "Run tests and ecosystem audit before every push.",
                "Promote only modules with an entrypoint, contract and tests.",
                "Never enable cloud fallback automatically.",
            ],
        }

    def snapshot(self) -> dict[str, Any]:
        modules = [module.to_dict() for module in self.modules()]
        upkeep = self.upkeep_report()
        healthy = sum(module["health"] == "healthy" for module in modules)
        return {
            "schema_version": 1,
            "ecosystem": self.manifest.get("ecosystem", {}),
            "summary": {
                "modules_total": len(modules),
                "modules_healthy": healthy,
                "modules_building": sum(module["health"] == "building" for module in modules),
                "modules_locked": sum(module["health"] == "locked" for module in modules),
                "upkeep_status": upkeep["status"],
            },
            "cost": self.cost_posture(),
            "modules": modules,
            "rotation": self.rotation_matrix(),
            "upkeep": upkeep,
        }
