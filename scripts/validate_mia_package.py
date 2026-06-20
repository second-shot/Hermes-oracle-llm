#!/usr/bin/env python3
"""Validate a local MIA/Hermes package without network access.

Standard library only. Does not execute hermes_employee.py; it compiles it and
validates file/JSON shape.
"""
from __future__ import annotations

import argparse
import json
import py_compile
import sys
from pathlib import Path

REQUIRED_FILES = [
    "hermes_employee.py",
    "data/employee/tasks.json",
    "data/employee/approvals.json",
    "data/employee/heartbeat.json",
    "data/employee/scoreboard.json",
    "data/security/security_scoreboard.json",
    "data/sources/source_registry.json",
    "skills/skill_registry.json",
    "docs/SECURITY_BOUNDARIES.md",
    "docs/ETHICAL_HACKING_MODE.md",
    "docs/SPEC-001-MIA-Local-Operator-Runtime.md",
    "policies/risk_policy.json",
    "policies/approval_policy.json",
    "policies/source_trust_policy.json",
    "policies/command_allowlist.json",
]

JSON_FILES = [
    "data/employee/tasks.json",
    "data/employee/approvals.json",
    "data/employee/heartbeat.json",
    "data/employee/scoreboard.json",
    "data/employee/bonus_ledger.json",
    "data/security/security_scoreboard.json",
    "data/sources/source_registry.json",
    "data/sources/source_log.json",
    "data/sources/source_cache.json",
    "skills/skill_registry.json",
    "policies/risk_policy.json",
    "policies/approval_policy.json",
    "policies/source_trust_policy.json",
    "policies/command_allowlist.json",
    "skills/godmode_core_polished.json",
]

REQUIRED_COMMANDS = [
    "status", "add", "tick", "run-once", "loop", "approve", "complete",
    "character", "rights", "skills", "sources", "route", "best",
    "source-plan", "security", "ethical-check", "threat-model",
    "secret-scan", "harden-plan", "security-check",
]

FORBIDDEN_SCRIPT_PATTERNS = [
    "Remove-Item -Recurse -Force",
    "rm -rf",
    "del /s /q",
    "git push --force",
]


def fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    raise SystemExit(1)


def ok(msg: str) -> None:
    print(f"OK: {msg}")


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"Invalid JSON {path}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", nargs="?", default=".")
    args = parser.parse_args()

    root = Path(args.repo).resolve()
    if not root.exists():
        fail(f"Repo not found: {root}")

    for rel in REQUIRED_FILES:
        path = root / rel
        if not path.exists():
            fail(f"Missing required file: {rel}")
    ok("required files exist")

    for rel in JSON_FILES:
        path = root / rel
        if path.exists():
            load_json(path)
    ok("JSON files parse")

    py_file = root / "hermes_employee.py"
    try:
        py_compile.compile(str(py_file), doraise=True)
    except Exception as exc:
        fail(f"Python compile failed: {exc}")
    ok("hermes_employee.py compiles")

    source = py_file.read_text(encoding="utf-8", errors="ignore")
    missing_commands = [cmd for cmd in REQUIRED_COMMANDS if f'"{cmd}"' not in source and f"'{cmd}'" not in source]
    if missing_commands:
        fail("Missing command strings in parser/source: " + ", ".join(missing_commands))
    ok("required CLI command names present")

    policies = {
        "risk_policy": load_json(root / "policies/risk_policy.json"),
        "approval_policy": load_json(root / "policies/approval_policy.json"),
        "source_trust_policy": load_json(root / "policies/source_trust_policy.json"),
        "command_allowlist": load_json(root / "policies/command_allowlist.json"),
    }

    if not policies["risk_policy"].get("high_risk_keywords"):
        fail("risk_policy.high_risk_keywords is empty")
    if not policies["approval_policy"].get("never_execute"):
        fail("approval_policy.never_execute is empty")
    if policies["command_allowlist"].get("network_commands_allowed_by_default") is not False:
        fail("network must not be allowed by default")
    ok("policy guardrails present")

    for script in (root / "scripts").glob("*.ps1"):
        text = script.read_text(encoding="utf-8", errors="ignore")
        for pattern in FORBIDDEN_SCRIPT_PATTERNS:
            if pattern in text:
                fail(f"Forbidden shell pattern in {script}: {pattern}")
    ok("PowerShell scripts do not contain forbidden destructive patterns")

    print("MIA package validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
