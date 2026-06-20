#!/usr/bin/env python3
"""
Hermes Employee / MIA Local Operator Runtime
Local-first CLI entrypoint for the Hermes overlay.
No paid API keys. No cloud calls. No shell execution.
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
]

DANGEROUS_TERMS = [
    "delete",
    "format",
    "wipe",
    "rm -rf",
    "del /s",
    "rmdir",
    "shutdown",
    "password",
    "token",
    "api key",
    "secret",
    "credential",
    "private key",
    "send money",
    "bank transfer",
    "execute shell",
    "run command",
]

FAST_TERMS = ["status", "list", "show", "summarise", "summarize", "check", "read"]
BUILD_TERMS = ["build", "create", "implement", "write", "patch", "fix", "test", "commit", "push"]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(relative_path: str, default: Any = None) -> Any:
    path = ROOT / relative_path
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # keep CLI alive; report bad JSON safely
        return {"_error": f"Failed to read {relative_path}: {exc}"}


def emit(data: Dict[str, Any]) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def append_event(event: Dict[str, Any]) -> None:
    STATE_DIR.mkdir(exist_ok=True)
    event.setdefault("timestamp", now_iso())
    with EVENT_LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def file_report() -> List[Dict[str, Any]]:
    return [
        {
            "path": rel,
            "exists": (ROOT / rel).exists(),
        }
        for rel in REQUIRED_FILES
    ]


def command_status(_: argparse.Namespace) -> int:
    files = file_report()
    missing = [item["path"] for item in files if not item["exists"]]
    emit(
        {
            "runtime": "hermes_employee",
            "mode": "local_first",
            "cloud": "disabled_by_default",
            "paid_api_required": False,
            "repo": str(ROOT),
            "state_log": str(EVENT_LOG),
            "required_files_ok": not missing,
            "missing_files": missing,
            "files": files,
            "timestamp": now_iso(),
        }
    )
    append_event({"type": "status", "ok": not missing, "missing": missing})
    return 0 if not missing else 1


def command_character(_: argparse.Namespace) -> int:
    skill = load_json("skills/godmode_core_polished.json", {})
    emit(
        {
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
            "skill_preview_keys": sorted(list(skill.keys()))[:20] if isinstance(skill, dict) else [],
        }
    )
    append_event({"type": "character", "ok": True})
    return 0


def command_security(_: argparse.Namespace) -> int:
    approval = load_json("policies/approval_policy.json", {})
    allowlist = load_json("policies/command_allowlist.json", {})
    risk = load_json("policies/risk_policy.json", {})
    source_trust = load_json("policies/source_trust_policy.json", {})
    emit(
        {
            "security_mode": "guarded_local",
            "shell_execution": "disabled_in_this_cli",
            "network_access": "not_performed_by_this_cli",
            "cloud_access": "disabled_by_default",
            "secrets_policy": "never_print_or_store_secrets",
            "policies_loaded": {
                "approval_policy": bool(approval),
                "command_allowlist": bool(allowlist),
                "risk_policy": bool(risk),
                "source_trust_policy": bool(source_trust),
            },
            "policy_errors": {
                name: value.get("_error")
                for name, value in {
                    "approval_policy": approval,
                    "command_allowlist": allowlist,
                    "risk_policy": risk,
                    "source_trust_policy": source_trust,
                }.items()
                if isinstance(value, dict) and value.get("_error")
            },
        }
    )
    append_event({"type": "security", "ok": True})
    return 0


def classify_request(text: str) -> Dict[str, Any]:
    lowered = text.lower().strip()
    dangerous_hits = [term for term in DANGEROUS_TERMS if term in lowered]
    fast_hits = [term for term in FAST_TERMS if term in lowered]
    build_hits = [term for term in BUILD_TERMS if term in lowered]

    if dangerous_hits:
        risk = "high"
        approval_required = True
        route = "approval_gate"
    elif build_hits:
        risk = "medium"
        approval_required = False
        route = "builder"
    elif fast_hits:
        risk = "low"
        approval_required = False
        route = "fast_local"
    else:
        risk = "low"
        approval_required = False
        route = "clarify_or_plan"

    complexity = min(10, max(1, len(text.split()) // 12 + len(build_hits) * 2 + len(dangerous_hits) * 4))

    return {
        "input": text,
        "route": route,
        "risk": risk,
        "approval_required": approval_required,
        "complexity_score": complexity,
        "matched_terms": {
            "dangerous": dangerous_hits,
            "build": build_hits,
            "fast": fast_hits,
        },
        "next_action": "refuse_auto_execution_and_request_approval" if approval_required else "prepare_local_next_step",
    }


def command_tick(args: argparse.Namespace) -> int:
    text = " ".join(args.text).strip() if args.text else "status check local runtime"
    result = classify_request(text)
    emit(
        {
            "tick": "ok",
            "runtime": "hermes_employee",
            "decision": result,
            "note": "This CLI classifies and records intent. It does not execute shell commands or call paid APIs.",
        }
    )
    append_event({"type": "tick", "decision": result})
    return 0


def command_validate(_: argparse.Namespace) -> int:
    missing = [item["path"] for item in file_report() if not item["exists"]]
    bad_json = []
    for rel in [
        "policies/approval_policy.json",
        "policies/command_allowlist.json",
        "policies/risk_policy.json",
        "policies/source_trust_policy.json",
        "schemas/task.schema.json",
        "schemas/event.schema.json",
        "schemas/approval.schema.json",
        "skills/godmode_core_polished.json",
    ]:
        loaded = load_json(rel, {})
        if isinstance(loaded, dict) and loaded.get("_error"):
            bad_json.append({"path": rel, "error": loaded["_error"]})

    ok = not missing and not bad_json
    emit({"validate": "ok" if ok else "fail", "missing": missing, "bad_json": bad_json})
    append_event({"type": "validate", "ok": ok, "missing": missing, "bad_json": bad_json})
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hermes Employee / MIA local operator runtime")
    sub = parser.add_subparsers(dest="command")

    p_status = sub.add_parser("status", help="Show runtime and file status")
    p_status.set_defaults(func=command_status)

    p_character = sub.add_parser("character", help="Show MIA operator character")
    p_character.set_defaults(func=command_character)

    p_security = sub.add_parser("security", help="Show guardrail/security mode")
    p_security.set_defaults(func=command_security)

    p_tick = sub.add_parser("tick", help="Classify one local task/request")
    p_tick.add_argument("text", nargs="*", help="Optional task text")
    p_tick.set_defaults(func=command_tick)

    p_validate = sub.add_parser("validate", help="Validate required overlay files")
    p_validate.set_defaults(func=command_validate)

    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        args = parser.parse_args(["status"])
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
