from __future__ import annotations

import importlib
import json
from pathlib import Path

from memory import store as memory_store


def test_memory_store_uses_runtime_root_and_redacts_logs(monkeypatch, tmp_path: Path) -> None:
    runtime = tmp_path / "runtime"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    monkeypatch.setenv("HERMES_DATA_DIR", str(runtime))
    module = importlib.reload(memory_store)
    module.REPO_ROOT = repo_root

    module.update_memory({"task_type": "text_reasoning"}, {"result": "ok"})
    module.log_session("hello", {"token": "secret-value-123"})

    structured = runtime / "memory" / "structured.json"
    sessions = runtime / "logs" / "sessions.md"

    assert structured.exists()
    assert json.loads(structured.read_text(encoding="utf-8"))["text_reasoning"]["result"] == "ok"
    assert sessions.exists()
    assert "secret-value-123" not in sessions.read_text(encoding="utf-8")
    assert not (Path(__file__).resolve().parents[1] / "memory" / "new-runtime-file.json").exists()
