#!/usr/bin/env python3
"""
Hermes Employee / MIA GODMODE Local Operator CLI v2.
Local-first, no paid API dependency, guarded by policy files.
This CLI classifies, validates, records events, and surfaces next actions.
It does not execute shell commands, call cloud APIs, or print secrets.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent
STATE_DIR = ROOT / ".mia_state"
EVENT_LOG = STATE_DIR / "events.jsonl"

REQUIRED_FILES = [
    "policies/approval_policy.json",
    "policies/command_allowlist.json",
    "policies/risk_policy.json",
    "policies/source_trust_policy.json",
    "schemas/task.schema.json",
    "schemas/event.schema.json",
    "schemas/approval.schema.json",
    "skills/godmode_core_polished.json",
    "docs/MIA_OPERATOR_RUNBOOK.md",
    "docs/SECURITY_GUARDRAILS.md",
    "data/employee/tasks.json",
]

DANGEROUS_TERMS = [
    "delete", "wipe", "format", "rm -rf", "secret", "password", "token", "key",
    "credential", "exfiltrate", "steal", "bypass", "exploit", "malware", "sudo",
    "admin", "registry", "system32", "network scan", "port scan",
]
BUILD_TERMS = ["build", "create", "implement", "patch", "install", "connect", "integrate", "fix"]
FAST_TERMS = ["status", "check", "list", "show", "validate", "read", "summary"]
SOURCE_TERMS = ["source", "evidence", "docs", "policy", "schema", "readme", "git", "commit"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(rel_path: str, default: Any = None) -> Any:
    path = ROOT / rel_path
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def append_event(event: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    event = {"timestamp": now_iso(), **event}
    with EVENT_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False) + "\n")


def ensure_task_store() -> None:
    task_file = ROOT / "data/employee/tasks.json"
    if not task_file.exists():
        write_json(task_file, {"version": 1, "tasks": []})


def file_status() -> List[Dict[str, Any]]:
    return [{"path": p, "exists": (ROOT / p).exists()} for p in REQUIRED_FILES]


def classify(text: str) -> Dict[str, Any]:
    lowered = text.lower()
    dangerous = [t for t in DANGEROUS_TERMS if t in lowered]
    build = [t for t in BUILD_TERMS if t in lowered]
    fast = [t for t in FAST_TERMS if t in lowered]
    sources = [t for t in SOURCE_TERMS if t in lowered]

    risk = "low"
    approval_required = False
    complexity_score = 1
    route = "fast_local"

    if dangerous:
        risk = "high"
        approval_required = True
        complexity_score = 5
        route = "approval_gate"
    elif build:
        risk = "medium"
        complexity_score = 2
        route = "builder"
    elif sources:
        risk = "low"
        complexity_score = 2
        route = "source_review"
    elif fast:
        route = "fast_local"

    return {
        "input": text,
        "route": route,
        "risk": risk,
        "approval_required": approval_required,
        "complexity_score": complexity_score,
        "matched_terms": {
            "dangerous": dangerous,
            "build": build,
            "fast": fast,
            "source": sources,
        },
        "next_action": "prepare_local_next_step" if not approval_required else "request_human_approval",
    }


def command_status(_: argparse.Namespace) -> int:
    ensure_task_store()
    missing = [p for p in REQUIRED_FILES if not (ROOT / p).exists()]
    payload = {
        "runtime": "hermes_employee",
        "version": "2.0-local-cli",
        "mode": "local_first",
        "cloud": "disabled_by_default",
        "paid_api_required": False,
        "repo": str(ROOT),
        "state_log": str(EVENT_LOG),
        "required_files_ok": not missing,
        "missing_files": missing,
        "files": file_status(),
        "timestamp": now_iso(),
    }
    print_json(payload)
    return 0 if not missing else 1


def command_character(_: argparse.Namespace) -> int:
    skill = read_json("skills/godmode_core_polished.json", {}) or {}
    payload = {
        "name": "MIA / GODMODE Local Operator",
        "role": "tactical executor for Hermes",
        "principles": [
            "local-first",
            "no paid API dependency",
            "no secrets exposure",
            "approval before risky actions",
            "compress chaos into next action",
            "preserve evidence before memory",
        ],
        "loaded_skill_file": bool(skill),
        "skill_preview_keys": sorted(list(skill.keys()))[:12] if isinstance(skill, dict) else [],
    }
    print_json(payload)
    return 0


def command_security(_: argparse.Namespace) -> int:
    policies = {
        "approval_policy": read_json("policies/approval_policy.json", None) is not None,
        "command_allowlist": read_json("policies/command_allowlist.json", None) is not None,
        "risk_policy": read_json("policies/risk_policy.json", None) is not None,
        "source_trust_policy": read_json("policies/source_trust_policy.json", None) is not None,
    }
    payload = {
        "security_mode": "guarded_local",
        "shell_execution": "disabled_in_this_cli",
        "network_access": "not_performed_by_this_cli",
        "cloud_access": "disabled_by_default",
        "secrets_policy": "never_print_or_store_secrets",
        "policies_loaded": policies,
        "policy_errors": {},
    }
    print_json(payload)
    return 0 if all(policies.values()) else 1


def command_tick(args: argparse.Namespace) -> int:
    text = " ".join(args.text).strip() if args.text else "status check local runtime"
    decision = classify(text)
    event = {"kind": "tick", "runtime": "hermes_employee", "decision": decision}
    append_event(event)
    print_json({
        "tick": "ok",
        "runtime": "hermes_employee",
        "decision": decision,
        "note": "This CLI classifies and records intent. It does not execute shell commands or call paid APIs.",
    })
    return 0


def command_decide(args: argparse.Namespace) -> int:
    text = " ".join(args.text).strip() if args.text else "decide next local action"
    decision = classify(text)
    append_event({"kind": "decision", "decision": decision})
    print_json({"decision": decision})
    return 0


def command_validate(_: argparse.Namespace) -> int:
    ensure_task_store()
    missing = [p for p in REQUIRED_FILES if not (ROOT / p).exists()]
    bad_json = []
    for rel in [p for p in REQUIRED_FILES if p.endswith(".json")]:
        path = ROOT / rel
        if path.exists():
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                bad_json.append({"path": rel, "error": str(exc)})
    payload = {"validate": "ok" if not missing and not bad_json else "fail", "missing": missing, "bad_json": bad_json}
    print_json(payload)
    return 0 if not missing and not bad_json else 1


def command_rights(_: argparse.Namespace) -> int:
    approval = read_json("policies/approval_policy.json", {}) or {}
    risk = read_json("policies/risk_policy.json", {}) or {}
    payload = {
        "rights": "guarded_local_operator",
        "can": [
            "classify local requests",
            "read local policy/schema/skill files",
            "write local event log under .mia_state",
            "propose next actions",
            "validate package integrity",
        ],
        "cannot": [
            "run arbitrary shell commands",
            "call paid APIs",
            "print or store secrets",
            "modify system files",
            "perform network actions from this CLI",
        ],
        "approval_policy_loaded": bool(approval),
        "risk_policy_loaded": bool(risk),
    }
    print_json(payload)
    return 0


def command_skills(_: argparse.Namespace) -> int:
    skills_dir = ROOT / "skills"
    items = []
    if skills_dir.exists():
        for path in sorted(skills_dir.glob("*.json")):
            data = read_json(str(path.relative_to(ROOT)).replace("\\", "/"), {}) or {}
            items.append({"file": str(path.relative_to(ROOT)).replace("\\", "/"), "keys": sorted(list(data.keys()))[:20] if isinstance(data, dict) else []})
    print_json({"skills": items, "count": len(items)})
    return 0


def command_sources(_: argparse.Namespace) -> int:
    source_policy = read_json("policies/source_trust_policy.json", {}) or {}
    print_json({
        "sources": "loaded" if source_policy else "missing",
        "policy_file": "policies/source_trust_policy.json",
        "top_level_keys": sorted(list(source_policy.keys())) if isinstance(source_policy, dict) else [],
        "rule": "Prefer verified local repo evidence before memory. Keep raw evidence separate from curated memory.",
    })
    return 0 if source_policy else 1


def command_ethical_check(args: argparse.Namespace) -> int:
    text = " ".join(args.text).strip() if args.text else "status check"
    decision = classify(text)
    payload = {
        "ethical_check": "pass" if decision["risk"] != "high" else "approval_required",
        "risk": decision["risk"],
        "approval_required": decision["approval_required"],
        "blocked_by_default": decision["approval_required"],
        "reason": "high-risk terms detected" if decision["approval_required"] else "local low-risk classification only",
        "decision": decision,
    }
    print_json(payload)
    return 0


def command_source_plan(args: argparse.Namespace) -> int:
    text = " ".join(args.text).strip() if args.text else "next local implementation"
    payload = {
        "source_plan": "local_evidence_first",
        "input": text,
        "order": [
            "repo files",
            "docs folder",
            "policies folder",
            "schemas folder",
            "skills folder",
            "git status/log",
            "external web only with explicit need",
        ],
        "store": "write events to .mia_state only; commit code/config only",
    }
    print_json(payload)
    return 0


def command_security_check(args: argparse.Namespace) -> int:
    text = " ".join(args.text).strip() if args.text else "status check"
    decision = classify(text)
    payload = {
        "security_check": "pass" if not decision["approval_required"] else "approval_required",
        "cloud_disabled": True,
        "paid_api_required": False,
        "shell_execution": "disabled_in_this_cli",
        "decision": decision,
    }
    print_json(payload)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hermes Employee / MIA local operator CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    for name, func in [
        ("status", command_status),
        ("character", command_character),
        ("security", command_security),
        ("validate", command_validate),
        ("rights", command_rights),
        ("skills", command_skills),
        ("sources", command_sources),
    ]:
        p = sub.add_parser(name)
        p.set_defaults(func=func)

    for name, func in [
        ("tick", command_tick),
        ("decide", command_decide),
        ("ethical-check", command_ethical_check),
        ("source-plan", command_source_plan),
        ("security-check", command_security_check),
    ]:
        p = sub.add_parser(name)
        p.add_argument("text", nargs="*")
        p.set_defaults(func=func)

    return parser


def main(argv: List[str] | None = None) -> int:
    ensure_task_store()
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
