from __future__ import annotations

import subprocess
from pathlib import Path


def test_runtime_paths_are_ignored_and_fixture_is_not() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    ignored = [
        ".hermes/cache/exact.json",
        "memory/structured.json",
        "memory/logs.md",
        "data/employee/heartbeat.json",
        "data/security/security_report.md",
        "data/sources/source_log.json",
        ".env.local",
        "tmp-runtime.tmp",
    ]
    for path in ignored:
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", path],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, path

    kept = subprocess.run(
        ["git", "check-ignore", "--no-index", "tests/fixtures/runtime-state/.gitkeep"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert kept.returncode != 0
