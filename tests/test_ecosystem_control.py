from __future__ import annotations

import json
from pathlib import Path

from backend.services.ecosystem_control import EcosystemControlPlane


def test_ecosystem_snapshot_reports_zero_cost_and_locked_cloud() -> None:
    snapshot = EcosystemControlPlane().snapshot()

    assert snapshot["cost"]["default_cost_usd"] == 0
    assert snapshot["cost"]["cloud_auto_fallback"] is False
    assert snapshot["cost"]["cloud_locked"] is True
    assert snapshot["cost"]["paid_models_allowed"] is False
    assert snapshot["summary"]["modules_total"] >= 8
    assert snapshot["upkeep"]["status"] == "pass"


def test_active_module_with_missing_file_blocks_upkeep(tmp_path: Path) -> None:
    manifest = {
        "schema_version": 1,
        "ecosystem": {"name": "test"},
        "modules": [
            {
                "id": "broken",
                "name": "Broken",
                "group": "test",
                "status": "active",
                "description": "Missing its contract.",
                "entrypoint": "missing.py",
                "required_files": ["missing.py"],
                "test_files": [],
                "upkeep": "Every pull request",
            }
        ],
    }
    manifest_path = tmp_path / "modules.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    rotation_path = Path(__file__).resolve().parents[1] / "config" / "hermes.model.rotation.yaml"

    snapshot = EcosystemControlPlane(
        project_root=tmp_path,
        manifest_path=manifest_path,
        rotation_path=rotation_path,
    ).snapshot()

    assert snapshot["upkeep"]["status"] == "fail"
    assert snapshot["modules"][0]["health"] == "attention"
    assert snapshot["upkeep"]["blockers"][0]["module"] == "broken"


def test_rotation_matrix_has_local_task_routes() -> None:
    routes = EcosystemControlPlane().rotation_matrix()

    route_names = {route["route"] for route in routes}
    assert {"simple_chat", "repo_debug", "code_patch", "screenshot_or_image"} <= route_names
