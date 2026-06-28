from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_status_uses_isolated_runtime_root(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    runtime = tmp_path / "runtime"
    tracked_files = [
        repo_root / "data" / "employee" / "heartbeat.json",
        repo_root / "data" / "security" / "security_report.md",
        repo_root / "data" / "sources" / "source_log.json",
    ]
    before = {path: path.stat().st_mtime_ns for path in tracked_files if path.exists()}
    env = os.environ.copy()
    env["HERMES_DATA_DIR"] = str(runtime)

    result = subprocess.run(
        [sys.executable, "hermes_employee.py", "status"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (runtime / "employee" / "heartbeat.json").exists()
    assert (runtime / "security" / "security_report.md").exists()
    assert (runtime / "sources" / "source_registry.json").exists()
    after = {path: path.stat().st_mtime_ns for path in tracked_files if path.exists()}
    assert before == after
