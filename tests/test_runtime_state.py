from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime_state import (
    atomic_write_json,
    migrate_legacy_state,
    redact_text,
    resolve_data_root,
)


def test_environment_override_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    override = tmp_path / "custom"
    monkeypatch.setenv("HERMES_DATA_DIR", str(override))

    assert resolve_data_root() == override.resolve()


def test_windows_local_appdata_is_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("HERMES_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))

    assert resolve_data_root() == (tmp_path / "Hermes").resolve()


def test_migrate_legacy_state_copies_known_files_without_deleting_source(tmp_path: Path) -> None:
    legacy_root = tmp_path / "legacy"
    data_root = tmp_path / "runtime"
    (legacy_root / "memory").mkdir(parents=True)
    (legacy_root / "data" / "employee").mkdir(parents=True)
    (legacy_root / "data" / "security").mkdir(parents=True)
    (legacy_root / "data" / "sources").mkdir(parents=True)
    (legacy_root / "memory" / "structured.json").write_text('{"note":"hello"}', encoding="utf-8")
    (legacy_root / "memory" / "logs.md").write_text("legacy log", encoding="utf-8")
    (legacy_root / "data" / "employee" / "tasks.json").write_text("[]", encoding="utf-8")
    (legacy_root / "data" / "security" / "security_report.md").write_text("report", encoding="utf-8")
    (legacy_root / "data" / "sources" / "source_log.json").write_text("[]", encoding="utf-8")

    migrate_legacy_state(legacy_root, data_root)

    assert (data_root / "memory" / "structured.json").read_text(encoding="utf-8") == '{"note":"hello"}'
    assert (data_root / "logs" / "sessions.md").read_text(encoding="utf-8") == "legacy log"
    assert (data_root / "employee" / "tasks.json").read_text(encoding="utf-8") == "[]"
    assert (legacy_root / "memory" / "structured.json").exists()
    marker = json.loads((data_root / "migration.json").read_text(encoding="utf-8"))
    assert marker["version"] == 1


def test_migrate_legacy_state_destination_wins_and_reruns_are_idempotent(tmp_path: Path) -> None:
    legacy_root = tmp_path / "legacy"
    data_root = tmp_path / "runtime"
    (legacy_root / "memory").mkdir(parents=True)
    (legacy_root / "memory" / "structured.json").write_text('{"legacy": true}', encoding="utf-8")
    (data_root / "memory").mkdir(parents=True)
    (data_root / "memory" / "structured.json").write_text('{"runtime": true}', encoding="utf-8")

    migrate_legacy_state(legacy_root, data_root)
    first = (data_root / "memory" / "structured.json").read_text(encoding="utf-8")
    migrate_legacy_state(legacy_root, data_root)
    second = (data_root / "memory" / "structured.json").read_text(encoding="utf-8")

    assert first == '{"runtime": true}'
    assert second == first


def test_migrate_legacy_state_does_not_write_completion_marker_on_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import runtime_state

    legacy_root = tmp_path / "legacy"
    data_root = tmp_path / "runtime"
    (legacy_root / "memory").mkdir(parents=True)
    (legacy_root / "memory" / "structured.json").write_text('{"legacy": true}', encoding="utf-8")

    def fail_once(*_args, **_kwargs):
        raise RuntimeError("copy failed")

    monkeypatch.setattr(runtime_state, "_copy_file_if_missing", fail_once)

    with pytest.raises(RuntimeError):
        migrate_legacy_state(legacy_root, data_root)

    assert not (data_root / "migration.json").exists()


def test_atomic_json_write_replaces_document(tmp_path: Path) -> None:
    path = tmp_path / "state.json"

    atomic_write_json(path, {"version": 1})
    atomic_write_json(path, {"version": 2})

    assert json.loads(path.read_text(encoding="utf-8")) == {"version": 2}
    assert list(tmp_path.glob("*.tmp")) == []


@pytest.mark.parametrize(
    "value",
    [
        "Authorization: Bearer abcdefghijklmnop",
        "api_key=abcdefghijklmnop",
        "password: supersecret123",
        "sk-abcdefghijklmnopqrstuvwxyz",
    ],
)
def test_redact_masks_secret_values(value: str) -> None:
    redacted = redact_text(value)

    assert "abcdefghijklmnop" not in redacted
    assert "supersecret123" not in redacted
    assert "abcdefghijklmnopqrstuvwxyz" not in redacted
