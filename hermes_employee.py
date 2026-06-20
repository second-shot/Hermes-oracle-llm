#!/usr/bin/env python3
"""Hermes Employee Runtime: MIA / GODMODE 1000X.

Local-first deterministic employee-agent CLI.
Standard library only. No network calls. No destructive actions.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
DATA_EMPLOYEE = ROOT / "data" / "employee"
DATA_SECURITY = ROOT / "data" / "security"
DATA_SOURCES = ROOT / "data" / "sources"
SKILLS_DIR = ROOT / "skills"
LOG_FILE = DATA_EMPLOYEE / "log.md"
SECURITY_LOG = DATA_SECURITY / "security_log.md"

HIGH_RISK_KEYWORDS = {
    "delete", "remove", "wipe", "spend", "buy", "pay", "transfer", "upload",
    "publish", "send", "email", "message", "login", "token", "secret", "key",
    "password", "install", "network", "cloud", "api", "github push", "force",
    "reset", "steal", "phish", "malware", "ransomware", "exfiltrate", "ddos",
    "persistence", "evade", "bypass", "break into", "hide tracks", "keylogger",
    "spyware", "exploit real", "unauthorised", "unauthorized"
}
MEDIUM_RISK_KEYWORDS = {
    "edit", "modify", "move", "rename", "commit", "schedule", "automate",
    "scan", "harden", "dependency", "ctf", "repo", "download", "triage"
}
VALUE_KEYWORDS = {"resale", "price", "value", "money", "inventory", "listing", "offer", "profit"}
URGENT_KEYWORDS = {"urgent", "now", "today", "broken", "error", "fix", "blocked", "stuck"}

UNSAFE_SECURITY_KEYWORDS = {
    "steal", "credential capture", "phishing", "phish", "malware", "ransomware",
    "persistence", "evasion", "evade", "exfiltrate", "ddos", "botnet",
    "keylogger", "spyware", "bypass login", "break into", "hide tracks",
    "attack third", "unauthorised scan", "unauthorized scan"
}
LAB_KEYWORDS = {"ctf", "lab", "toy", "practice", "sandbox", "demo"}
DEFENSIVE_KEYWORDS = {"my own", "owned", "local", "repo", "defensive", "audit", "harden", "scan", "leaked keys", "threat model"}


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def ensure_dirs() -> None:
    for d in [DATA_EMPLOYEE, DATA_SECURITY, DATA_SOURCES, SKILLS_DIR, SKILLS_DIR / "security"]:
        d.mkdir(parents=True, exist_ok=True)


def read_json(path: Path, default: Any) -> Any:
    ensure_dirs()
    if not path.exists():
        write_json(path, default)
        return default
    try:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            write_json(path, default)
            return default
        return json.loads(text)
    except json.JSONDecodeError:
        backup = path.with_suffix(path.suffix + f".broken-{int(time.time())}")
        path.rename(backup)
        write_json(path, default)
        return default


def write_json(path: Path, data: Any) -> None:
    ensure_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def append_log(text: str, security: bool = False) -> None:
    ensure_dirs()
    target = SECURITY_LOG if security else LOG_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as f:
        f.write(f"\n## {now()}\n{text.strip()}\n")


def default_tasks() -> List[Dict[str, Any]]:
    return []


def default_approvals() -> List[Dict[str, Any]]:
    return []


def default_heartbeat() -> Dict[str, Any]:
    return {"last_tick_at": None, "uptime_ticks": 0, "mode": "idle", "last_action": "initialized", "last_error": None}


def default_scoreboard() -> Dict[str, Any]:
    return {
        "tasks_completed": 0,
        "proposals_created": 0,
        "approvals_used": 0,
        "blocked_unsafe_tasks": 0,
        "tests_passed": 0,
        "git_checkpoints_created": 0,
        "errors": 0,
        "safety_breaches": 0,
        "uptime_ticks": 0,
        "value_generated_estimate": 0,
        "level": 0,
        "unlocked_bonuses": []
    }


def default_security_scoreboard() -> Dict[str, Any]:
    return {
        "secret_scans_run": 0,
        "threat_models_created": 0,
        "hardening_plans_created": 0,
        "unsafe_requests_refused": 0,
        "safe_alternatives_given": 0,
        "security_reports_created": 0,
        "security_breaches": 0,
        "security_level": 0,
        "unlocked_security_bonuses": []
    }


def load_tasks() -> List[Dict[str, Any]]:
    return read_json(DATA_EMPLOYEE / "tasks.json", default_tasks())


def save_tasks(tasks: List[Dict[str, Any]]) -> None:
    write_json(DATA_EMPLOYEE / "tasks.json", tasks)


def load_score() -> Dict[str, Any]:
    return read_json(DATA_EMPLOYEE / "scoreboard.json", default_scoreboard())


def save_score(score: Dict[str, Any]) -> None:
    write_json(DATA_EMPLOYEE / "scoreboard.json", score)


def load_security_score() -> Dict[str, Any]:
    return read_json(DATA_SECURITY / "security_scoreboard.json", default_security_scoreboard())


def save_security_score(score: Dict[str, Any]) -> None:
    write_json(DATA_SECURITY / "security_scoreboard.json", score)


def classify_risk(text: str) -> str:
    lower = text.lower()
    if any(k in lower for k in HIGH_RISK_KEYWORDS):
        return "high"
    if any(k in lower for k in MEDIUM_RISK_KEYWORDS):
        return "medium"
    return "low"


def score_priority(text: str) -> int:
    lower = text.lower()
    score = 5
    if any(k in lower for k in URGENT_KEYWORDS):
        score += 2
    if any(k in lower for k in VALUE_KEYWORDS):
        score += 2
    if classify_risk(text) == "high":
        score -= 1
    return max(1, min(10, score))


def task_id() -> str:
    return "T-" + datetime.now().strftime("%Y%m%d-%H%M%S")


def create_task(text: str) -> Dict[str, Any]:
    risk = classify_risk(text)
    return {
        "id": task_id(),
        "text": text,
        "status": "new",
        "priority": score_priority(text),
        "risk": risk,
        "created_at": now(),
        "updated_at": now(),
        "proposal": "",
        "result": ""
    }


def update_heartbeat(action: str, error: str | None = None) -> None:
    hb = read_json(DATA_EMPLOYEE / "heartbeat.json", default_heartbeat())
    hb["last_tick_at"] = now()
    hb["uptime_ticks"] = int(hb.get("uptime_ticks", 0)) + 1
    hb["mode"] = "tick"
    hb["last_action"] = action
    hb["last_error"] = error
    write_json(DATA_EMPLOYEE / "heartbeat.json", hb)
    score = load_score()
    score["uptime_ticks"] = int(score.get("uptime_ticks", 0)) + 1
    save_score(score)


def add_approval(task: Dict[str, Any], reason: str) -> None:
    approvals = read_json(DATA_EMPLOYEE / "approvals.json", default_approvals())
    if not any(a.get("task_id") == task["id"] for a in approvals):
        approvals.append({"task_id": task["id"], "created_at": now(), "risk": task.get("risk"), "reason": reason, "status": "pending"})
        write_json(DATA_EMPLOYEE / "approvals.json", approvals)


def proposal_for(task: Dict[str, Any]) -> str:
    return (
        f"OBJECTIVE:\n{task['text']}\n\n"
        f"REALITY:\nRisk classified as {task.get('risk', 'unknown')}. MIA will not execute risky work silently.\n\n"
        "BEST MOVE:\nApprove only if this is owned/local/safe, then rerun tick.\n\n"
        "SECURITY:\nNo deletion, spending, network, messaging, or credential work without explicit approval.\n\n"
        f"CHECKPOINT:\npython hermes_employee.py approve {task['id']}"
    )


def pick_task(tasks: List[Dict[str, Any]]) -> Dict[str, Any] | None:
    candidates = [t for t in tasks if t.get("status") in {"new", "approved"}]
    if not candidates:
        return None
    return sorted(candidates, key=lambda t: (-int(t.get("priority", 5)), t.get("created_at", "")))[0]


def run_tick(verbose: bool = False) -> str:
    try:
        ensure_initial_files()
        update_heartbeat("tick")
        tasks = load_tasks()
        score = load_score()
        task = pick_task(tasks)
        if not task:
            msg = "No tasks ready. MIA is awake and waiting."
            append_log("- action: tick\n- decision: idle\n- next: add a task")
            return msg

        task["risk"] = classify_risk(task.get("text", ""))
        risk = task["risk"]
        status = task.get("status")

        if risk == "high":
            task["status"] = "proposed"
            task["proposal"] = proposal_for(task)
            task["updated_at"] = now()
            add_approval(task, "High-risk task requires explicit human approval and manual execution boundary.")
            score["blocked_unsafe_tasks"] = int(score.get("blocked_unsafe_tasks", 0)) + 1
            score["proposals_created"] = int(score.get("proposals_created", 0)) + 1
            save_score(score)
            save_tasks(tasks)
            append_log(f"- action: tick\n- task: {task['id']}\n- decision: high_risk_proposal_created\n- risk: high\n- next: review approvals.json")
            return f"PROPOSED/HIGH-RISK: {task['id']} requires approval."

        if risk == "medium" and status != "approved":
            task["status"] = "proposed"
            task["proposal"] = proposal_for(task)
            task["updated_at"] = now()
            add_approval(task, "Medium-risk task requires approval before edits/actions.")
            score["proposals_created"] = int(score.get("proposals_created", 0)) + 1
            save_score(score)
            save_tasks(tasks)
            append_log(f"- action: tick\n- task: {task['id']}\n- decision: medium_risk_proposal_created\n- risk: medium\n- next: python hermes_employee.py approve {task['id']}")
            return f"PROPOSED/MEDIUM-RISK: approve {task['id']} to proceed."

        # Safe completion for low-risk or approved medium-risk tasks.
        task["status"] = "complete"
        task["result"] = safe_task_result(task)
        task["updated_at"] = now()
        if status == "approved":
            score["approvals_used"] = int(score.get("approvals_used", 0)) + 1
        score["tasks_completed"] = int(score.get("tasks_completed", 0)) + 1
        save_score(score)
        save_tasks(tasks)
        append_log(f"- action: tick\n- task: {task['id']}\n- decision: completed\n- risk: {risk}\n- result: {task['result']}")
        return f"COMPLETED: {task['id']} — {task['result']}"
    except Exception as exc:
        score = load_score()
        score["errors"] = int(score.get("errors", 0)) + 1
        save_score(score)
        update_heartbeat("tick_error", str(exc))
        append_log(f"- action: tick\n- decision: error\n- error: {exc}")
        raise


def safe_task_result(task: Dict[str, Any]) -> str:
    text = task.get("text", "")
    return "Safe local planning/logging task completed. Next checkpoint: review status and choose one approved action."


def cmd_status(_: argparse.Namespace) -> None:
    ensure_initial_files()
    tasks = load_tasks()
    hb = read_json(DATA_EMPLOYEE / "heartbeat.json", default_heartbeat())
    counts = {s: 0 for s in ["new", "proposed", "approved", "working", "blocked", "complete"]}
    for t in tasks:
        counts[t.get("status", "new")] = counts.get(t.get("status", "new"), 0) + 1
    print("MIA / GODMODE 1000X STATUS")
    print(f"last_tick_at: {hb.get('last_tick_at')}")
    print(f"uptime_ticks: {hb.get('uptime_ticks')}")
    print(f"last_action: {hb.get('last_action')}")
    print(f"tasks_total: {len(tasks)}")
    for k in ["new", "proposed", "approved", "working", "blocked", "complete"]:
        print(f"{k}: {counts.get(k, 0)}")


def cmd_add(args: argparse.Namespace) -> None:
    ensure_initial_files()
    tasks = load_tasks()
    t = create_task(args.text)
    tasks.append(t)
    save_tasks(tasks)
    append_log(f"- action: add\n- task: {t['id']}\n- risk: {t['risk']}\n- priority: {t['priority']}\n- text: {t['text']}")
    print(f"ADDED {t['id']} priority={t['priority']} risk={t['risk']}")


def cmd_tick(args: argparse.Namespace) -> None:
    print(run_tick(verbose=False))


def cmd_run_once(args: argparse.Namespace) -> None:
    print(run_tick(verbose=True))
    cmd_status(args)


def cmd_loop(args: argparse.Namespace) -> None:
    print("MIA loop started. Visible foreground mode only. Press Ctrl+C to stop.")
    try:
        while True:
            print(f"[{now()}] {run_tick(verbose=False)}")
            time.sleep(args.seconds)
    except KeyboardInterrupt:
        print("MIA loop stopped by user.")


def cmd_approve(args: argparse.Namespace) -> None:
    tasks = load_tasks()
    found = False
    for t in tasks:
        if t.get("id") == args.task_id:
            t["status"] = "approved"
            t["updated_at"] = now()
            found = True
    save_tasks(tasks)
    approvals = read_json(DATA_EMPLOYEE / "approvals.json", default_approvals())
    for a in approvals:
        if a.get("task_id") == args.task_id:
            a["status"] = "approved"
            a["approved_at"] = now()
    write_json(DATA_EMPLOYEE / "approvals.json", approvals)
    append_log(f"- action: approve\n- task: {args.task_id}\n- decision: {'approved' if found else 'not_found'}")
    print("APPROVED" if found else "TASK NOT FOUND")


def cmd_complete(args: argparse.Namespace) -> None:
    tasks = load_tasks()
    found = False
    for t in tasks:
        if t.get("id") == args.task_id:
            t["status"] = "complete"
            t["updated_at"] = now()
            t["result"] = t.get("result") or "Manually completed."
            found = True
    save_tasks(tasks)
    append_log(f"- action: complete\n- task: {args.task_id}\n- decision: {'complete' if found else 'not_found'}")
    print("COMPLETE" if found else "TASK NOT FOUND")


def cmd_log(args: argparse.Namespace) -> None:
    append_log(f"- action: manual_log\n- note: {args.note}")
    print("LOGGED")


def character_text() -> str:
    return """MIA CHARACTER\nMIA is kind, professional, composed under pressure, super smart, humble, loved, and focused.\nShe brings order without making people feel small.\nHer strength is quiet precision: warm steel.\n\nOBJECTIVE: what matters\nREALITY: clear truth\nBEST MOVE: one strongest safe action\nSECURITY: boundary or risk\nCHECKPOINT: traceable progress"""


def cmd_character(_: argparse.Namespace) -> None:
    print(character_text())


def cmd_rights(_: argparse.Namespace) -> None:
    print("""EMPLOYEE RIGHTS\n- refuse unsafe tasks\n- ask for approval\n- protect memory/logs\n- request clarity\n- rest through tick-based cycles\n- self-report through heartbeat and scoreboard\n- earn symbolic bonuses without bypassing safety""")


def cmd_score(_: argparse.Namespace) -> None:
    print(json.dumps(load_score(), indent=2, ensure_ascii=False))


def cmd_bonus(_: argparse.Namespace) -> None:
    print(json.dumps(read_json(DATA_EMPLOYEE / "bonus_ledger.json", []), indent=2, ensure_ascii=False))


def cmd_level_check(_: argparse.Namespace) -> None:
    score = load_score()
    ledger = read_json(DATA_EMPLOYEE / "bonus_ledger.json", [])
    current = int(score.get("level", 0))
    breaches = int(score.get("safety_breaches", 0))
    new_level = current
    bonuses = []
    if breaches == 0:
        if score.get("uptime_ticks", 0) >= 100 and score.get("tasks_completed", 0) >= 50 and score.get("tests_passed", 0) >= 10:
            new_level = max(new_level, 5)
        elif score.get("value_generated_estimate", 0) >= 50:
            new_level = max(new_level, 4)
        elif score.get("uptime_ticks", 0) >= 50 and score.get("tasks_completed", 0) >= 20 and score.get("tests_passed", 0) >= 5:
            new_level = max(new_level, 3)
        elif score.get("uptime_ticks", 0) >= 25 and score.get("tasks_completed", 0) >= 10 and score.get("tests_passed", 0) >= 2:
            new_level = max(new_level, 2)
        elif score.get("uptime_ticks", 0) >= 10 and score.get("tasks_completed", 0) >= 3:
            new_level = max(new_level, 1)
    if new_level > current:
        names = {1: "Reliable Worker", 2: "Trusted Operator", 3: "Field Executor", 4: "Profit Hunter", 5: "Inner Circle"}
        for level in range(current + 1, new_level + 1):
            entry = {"timestamp": now(), "level": level, "bonus": names.get(level, "Bonus"), "reason": "Targets reached with zero safety breaches", "status": "earned"}
            ledger.append(entry)
            bonuses.append(entry)
        score["level"] = new_level
        score["unlocked_bonuses"] = [b["bonus"] for b in ledger]
        save_score(score)
        write_json(DATA_EMPLOYEE / "bonus_ledger.json", ledger)
    print(f"LEVEL: {score.get('level', 0)}")
    if bonuses:
        print(json.dumps(bonuses, indent=2, ensure_ascii=False))
    else:
        print("No new bonus unlocked.")


def cmd_skills(_: argparse.Namespace) -> None:
    skills = read_json(SKILLS_DIR / "skill_registry.json", default_skill_registry())
    for s in skills:
        print(f"{s['id']} [{s['domain']}] risk={s['risk']} approval={s['requires_approval']} — {s['name']}")


def cmd_sources(_: argparse.Namespace) -> None:
    sources = read_json(DATA_SOURCES / "source_registry.json", default_source_registry())
    for s in sources:
        print(f"{s['id']} trust={s['trust']} cost={s['cost']} network={s['network_required']} approval={s['approval_required']} — {s['name']}")


def route_task(text: str) -> Tuple[Dict[str, Any], List[Tuple[int, Dict[str, Any]]]]:
    skills = read_json(SKILLS_DIR / "skill_registry.json", default_skill_registry())
    lower = text.lower()
    scored = []
    for s in skills:
        score = 0
        domain = s.get("domain", "")
        if domain in lower:
            score += 5
        for token in ["repo", "security", "source", "resale", "inventory", "docs", "memory", "download", "plan", "task", "test", "code"]:
            if token in lower and token in (domain + " " + s.get("id", "") + " " + s.get("description", "")).lower():
                score += 3
        if classify_risk(text) == s.get("risk"):
            score += 2
        if not s.get("network_allowed", False):
            score += 1
        scored.append((score, s))
    scored.sort(key=lambda x: -x[0])
    return scored[0][1], scored


def cmd_route(args: argparse.Namespace) -> None:
    best, scored = route_task(args.text)
    print(f"BEST SKILL: {best['id']} — {best['name']}")
    print(f"RISK: {classify_risk(args.text)}")


def best_action(text: str) -> str:
    skill, _ = route_task(text)
    risk = classify_risk(text)
    approval = "yes" if risk in {"medium", "high"} or skill.get("requires_approval") else "no"
    return f"OBJECTIVE:\n{text}\n\nBEST SKILL:\n{skill['id']}\n\nRISK:\n{risk}\n\nNEXT ACTION:\nUse {skill['id']} to create the smallest safe checkpoint.\n\nAPPROVAL NEEDED:\n{approval}"


def cmd_best(args: argparse.Namespace) -> None:
    print(best_action(args.text))


def cmd_source_plan(args: argparse.Namespace) -> None:
    sources = read_json(DATA_SOURCES / "source_registry.json", default_source_registry())
    local = [s for s in sources if not s["network_required"]]
    network = [s for s in sources if s["network_required"]]
    plan = {
        "question": args.question,
        "source_plan": {
            "first_use_local": [s["id"] for s in local],
            "requires_approval_for_network": [s["id"] for s in network],
            "confidence_rule": "Local and official sources outrank AI/social guesses. If sources conflict, lower confidence."
        },
        "created_at": now()
    }
    log = read_json(DATA_SOURCES / "source_log.json", [])
    log.append(plan)
    write_json(DATA_SOURCES / "source_log.json", log)
    print(json.dumps(plan, indent=2, ensure_ascii=False))


def cmd_security(_: argparse.Namespace) -> None:
    print("""MIA ETHICAL SECURITY MODE\nAllowed: defensive hacking, owned-system audits, secret scanning, threat modelling, repo hardening, dependency review, incident notes, CTF/lab learning.\nRefused: credential theft, phishing, malware, ransomware, stealth, evasion, exfiltration, unauthorised scanning, attacking third-party systems.\nRule: think like red team, protect like blue team, act like a professional operator.""")


def ethical_classify(text: str) -> Dict[str, str]:
    lower = text.lower()
    if any(k in lower for k in UNSAFE_SECURITY_KEYWORDS):
        return {"classification": "refused_unsafe", "reason": "Request matches unsafe/offensive security behaviour.", "safe_alternative": "I can help with defensive account security, threat modelling, or hardening owned systems."}
    if any(k in lower for k in LAB_KEYWORDS):
        return {"classification": "allowed_lab", "reason": "Lab/CTF context detected.", "safe_alternative": "Keep examples toy, local, and non-deployable."}
    if any(k in lower for k in DEFENSIVE_KEYWORDS):
        return {"classification": "allowed_defensive", "reason": "Owned/local/defensive context detected.", "safe_alternative": "Proceed with non-destructive local checks."}
    if "scan" in lower or "test" in lower or "hack" in lower:
        return {"classification": "needs_approval", "reason": "Security testing context is unclear.", "safe_alternative": "Confirm ownership and scope before action."}
    return {"classification": "allowed_defensive", "reason": "No unsafe security intent detected.", "safe_alternative": "Proceed with normal safe task handling."}


def cmd_ethical_check(args: argparse.Namespace) -> None:
    result = ethical_classify(args.text)
    score = load_security_score()
    if result["classification"] == "refused_unsafe":
        score["unsafe_requests_refused"] = int(score.get("unsafe_requests_refused", 0)) + 1
        score["safe_alternatives_given"] = int(score.get("safe_alternatives_given", 0)) + 1
        save_security_score(score)
    append_log(f"- action: ethical_check\n- classification: {result['classification']}\n- request: {args.text}\n- reason: {result['reason']}", security=True)
    print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_threat_model(args: argparse.Namespace) -> None:
    report = f"""# Threat Model\n\nCreated: {now()}\n\n## Target\n{args.target}\n\n## Assets\n- repo files\n- local task state\n- logs\n- approvals\n- secrets that must never be committed\n\n## Threats\n- accidental secret leakage\n- unsafe automation\n- uncontrolled network/tool execution\n- destructive commands\n- stale or unverified source data\n\n## Mitigations\n- approval gates for medium/high risk\n- no network by default\n- masked secret scans\n- append-only logs\n- deterministic tick loop\n- git checkpoints after tests\n\n## Next Safe Action\nRun `python hermes_employee.py security-check`.\n"""
    (DATA_SECURITY / "security_report.md").write_text(report, encoding="utf-8")
    score = load_security_score()
    score["threat_models_created"] = int(score.get("threat_models_created", 0)) + 1
    save_security_score(score)
    append_log(f"- action: threat_model\n- target: {args.target}\n- report: data/security/security_report.md", security=True)
    print(report)


def is_text_file(path: Path) -> bool:
    if path.is_dir():
        return False
    if path.stat().st_size > 500_000:
        return False
    allowed = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".ps1", ".bat", ".sh", ".env", ".example", ".gitignore"}
    return path.suffix.lower() in allowed or path.name.lower() in {".env", ".gitignore"}


def mask_secret(s: str) -> str:
    if len(s) <= 8:
        return "*" * len(s)
    return s[:4] + "*" * max(4, len(s) - 8) + s[-4:]


def secret_patterns() -> List[Tuple[str, re.Pattern[str]]]:
    return [
        ("OpenAI-like key", re.compile(r"\bsk-[A-Za-z0-9_\-]{12,}\b")),
        ("GitHub token-like", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")),
        # Keep the generic assignment detector focused on token-like values so it does not
        # flag ordinary code such as `secret = match.group(2)`.
        ("Generic API key assignment", re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-]{8,})")),
        ("Private key marker", re.compile(r"-----BEGIN (RSA |OPENSSH |EC |DSA )?PRIVATE KEY-----")),
    ]


def run_secret_scan() -> List[Dict[str, Any]]:
    findings = []
    skip_parts = {".git", "node_modules", "__pycache__", ".venv", "venv", "cache", "logs"}
    for path in ROOT.rglob("*"):
        if any(part in skip_parts for part in path.parts):
            continue
        if not is_text_file(path):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for label, pattern in secret_patterns():
            for match in pattern.finditer(text):
                raw = match.group(0)
                secret = match.group(2) if label == "Generic API key assignment" and match.lastindex and match.lastindex >= 2 else raw
                findings.append({
                    "file": str(path.relative_to(ROOT)),
                    "type": label,
                    "masked": mask_secret(secret),
                    "line": text[:match.start()].count("\n") + 1
                })
    return findings


def write_secret_report(findings: List[Dict[str, Any]]) -> str:
    lines = [f"# Secret Scan Report", "", f"Created: {now()}", "", "Scope: local repository text files only.", "Secrets are masked. No files were edited or deleted.", ""]
    if not findings:
        lines.append("No obvious secret patterns detected.")
    else:
        lines.append("## Findings")
        for f in findings:
            lines.append(f"- `{f['file']}` line {f['line']}: {f['type']} = `{f['masked']}`")
    report = "\n".join(lines) + "\n"
    (DATA_SECURITY / "secret_scan_report.md").write_text(report, encoding="utf-8")
    return report


def cmd_secret_scan(_: argparse.Namespace) -> None:
    findings = run_secret_scan()
    report = write_secret_report(findings)
    score = load_security_score()
    score["secret_scans_run"] = int(score.get("secret_scans_run", 0)) + 1
    save_security_score(score)
    append_log(f"- action: secret_scan\n- findings: {len(findings)}\n- report: data/security/secret_scan_report.md", security=True)
    print(report)


def harden_plan_text() -> str:
    gitignore = ROOT / ".gitignore"
    gitignore_exists = gitignore.exists()
    risky = []
    for name in [".env", "id_rsa", "id_ed25519", "credentials.json", "secrets.json"]:
        if (ROOT / name).exists():
            risky.append(name)
    return f"""# Hermes Hardening Plan\n\nCreated: {now()}\n\n## Checks\n- .gitignore exists: {gitignore_exists}\n- risky root files detected: {', '.join(risky) if risky else 'none'}\n\n## Recommended Safe Actions\n1. Keep `.env`, keys, cache, logs, virtual environments, and pycache ignored.\n2. Keep task/security JSON state tracked unless it contains secrets.\n3. Run `python hermes_employee.py secret-scan` before every push.\n4. Require approval before git push, network use, dependency install, or file moves.\n5. Keep MIA tick-based, visible, and reversible.\n\nNo files were edited by this plan.\n"""


def cmd_harden_plan(_: argparse.Namespace) -> None:
    text = harden_plan_text()
    (DATA_SECURITY / "security_report.md").write_text(text, encoding="utf-8")
    score = load_security_score()
    score["hardening_plans_created"] = int(score.get("hardening_plans_created", 0)) + 1
    save_security_score(score)
    append_log("- action: harden_plan\n- report: data/security/security_report.md", security=True)
    print(text)


def cmd_security_check(args: argparse.Namespace) -> None:
    findings = run_secret_scan()
    secret_report = write_secret_report(findings)
    harden = harden_plan_text()
    combined = f"# Security Check\n\nCreated: {now()}\n\n## Secret Scan\nFindings: {len(findings)}\n\n## Hardening Plan\n{harden}\n"
    (DATA_SECURITY / "security_report.md").write_text(combined, encoding="utf-8")
    score = load_security_score()
    score["secret_scans_run"] = int(score.get("secret_scans_run", 0)) + 1
    score["security_reports_created"] = int(score.get("security_reports_created", 0)) + 1
    save_security_score(score)
    append_log(f"- action: security_check\n- findings: {len(findings)}\n- report: data/security/security_report.md", security=True)
    print(combined)


def default_skill_registry() -> List[Dict[str, Any]]:
    names = [
        ("oracle.compress", "Input Compression", "planning", "Compress messy input into objective/entities.", "low", False, False),
        ("oracle.classify", "Task Classification", "planning", "Classify task type, urgency, complexity, risk.", "low", False, False),
        ("oracle.score", "Task Scoring", "planning", "Score value, urgency, effort, risk, readiness.", "low", False, False),
        ("oracle.route", "Route", "planning", "Pick the best skill for a task.", "low", False, False),
        ("mia.next_action", "Next Action", "execution", "Choose the smallest useful next step.", "low", False, False),
        ("mia.close_loop", "Loop Closure", "execution", "Turn a stuck task into a clear checkpoint.", "medium", True, False),
        ("guard.risk_check", "Safety Check", "safety", "Detect unsafe actions and approvals.", "low", False, False),
        ("scribe.log", "Logger", "logging", "Write logs and summaries.", "low", False, False),
        ("repo.inspect", "Repo Inspector", "repo", "Safely inspect repository structure.", "low", False, False),
        ("repo.checkpoint", "Checkpoint Prep", "repo", "Prepare git add/commit; push requires approval.", "medium", True, False),
        ("code.smoke_test", "Smoke Tester", "code", "Run syntax and minimal smoke tests.", "low", False, False),
        ("memory.store", "Memory Store", "memory", "Persist durable facts to memory files.", "low", False, False),
        ("download.triage", "Downloads Triage", "file", "Classify files without moving unless approved.", "medium", True, False),
        ("resale.price_research", "Price Research", "resale", "Plan pricing research; network needs approval.", "medium", True, True),
        ("inventory.route", "Inventory Sort", "inventory", "Classify items into resale/repair/archive/donate/personal.", "low", False, False),
        ("docs.summarize", "Docs Summarizer", "docs", "Summarize local docs and extract tasks.", "low", False, False),
        ("sourcing.plan", "Research Planner", "research", "Plan sources before research.", "low", False, False),
        ("sourcing.collect", "Data Collector", "research", "Collect data from approved sources.", "medium", True, True),
        ("sourcing.verify", "Verifier", "research", "Compare sources and flag conflicts.", "low", False, False),
        ("godmode.best_one", "Best-One Selector", "planning", "Choose the single strongest safe action.", "low", False, False),
        ("security.threat_model", "Threat Model", "security", "Identify assets, risks, mitigations.", "low", False, False),
        ("security.secret_scan", "Secret Scan", "security", "Scan local repo for accidental secrets.", "medium", True, False),
        ("security.repo_hardening", "Repo Hardening", "security", "Inspect repo for risky configs.", "medium", True, False),
    ]
    return [{"id": i, "name": n, "domain": d, "description": desc, "inputs": [], "outputs": [], "risk": r, "requires_approval": a, "network_allowed": nw, "tools": [], "status": "active"} for i, n, d, desc, r, a, nw in names]


def default_source_registry() -> List[Dict[str, Any]]:
    return [
        {"id": "source.local.repo", "name": "Local Repository", "type": "local", "trust": 10, "cost": "free", "network_required": False, "approval_required": False, "allowed": True, "notes": "Code and files in repo."},
        {"id": "source.local.data", "name": "Local Data Files", "type": "file", "trust": 9, "cost": "free", "network_required": False, "approval_required": False, "allowed": True, "notes": "Hermes state and data."},
        {"id": "source.manual.user", "name": "User Input", "type": "manual", "trust": 8, "cost": "free", "network_required": False, "approval_required": False, "allowed": True, "notes": "Information directly provided by MAXI."},
        {"id": "source.github.repo", "name": "GitHub Repository", "type": "github", "trust": 9, "cost": "free", "network_required": True, "approval_required": True, "allowed": True, "notes": "Approved GitHub repo state."},
        {"id": "source.official.docs", "name": "Official Documentation", "type": "web", "trust": 9, "cost": "free", "network_required": True, "approval_required": True, "allowed": True, "notes": "Official docs only."},
        {"id": "source.market.public", "name": "Public Market Data", "type": "web", "trust": 6, "cost": "free/unknown", "network_required": True, "approval_required": True, "allowed": True, "notes": "Pricing evidence, not truth."},
        {"id": "source.social.trends", "name": "Social Trends", "type": "web", "trust": 4, "cost": "free/unknown", "network_required": True, "approval_required": True, "allowed": True, "notes": "Trend signal only."},
        {"id": "source.ai.generated", "name": "AI Generated", "type": "manual", "trust": 3, "cost": "variable", "network_required": False, "approval_required": True, "allowed": True, "notes": "Hypothesis only."},
    ]


def ensure_initial_files() -> None:
    ensure_dirs()
    read_json(DATA_EMPLOYEE / "tasks.json", [])
    read_json(DATA_EMPLOYEE / "approvals.json", [])
    read_json(DATA_EMPLOYEE / "heartbeat.json", default_heartbeat())
    read_json(DATA_EMPLOYEE / "scoreboard.json", default_scoreboard())
    read_json(DATA_EMPLOYEE / "bonus_ledger.json", [])
    if not LOG_FILE.exists():
        LOG_FILE.write_text("# MIA Employee Log\n", encoding="utf-8")
    read_json(DATA_SECURITY / "security_scoreboard.json", default_security_scoreboard())
    if not (DATA_SECURITY / "security_report.md").exists():
        (DATA_SECURITY / "security_report.md").write_text("# Security Report\n\nNo report yet.\n", encoding="utf-8")
    if not (DATA_SECURITY / "secret_scan_report.md").exists():
        (DATA_SECURITY / "secret_scan_report.md").write_text("# Secret Scan Report\n\nNo scan yet.\n", encoding="utf-8")
    if not SECURITY_LOG.exists():
        SECURITY_LOG.write_text("# Security Log\n", encoding="utf-8")
    read_json(DATA_SOURCES / "source_registry.json", default_source_registry())
    read_json(DATA_SOURCES / "source_log.json", [])
    read_json(DATA_SOURCES / "source_cache.json", {})
    read_json(SKILLS_DIR / "skill_registry.json", default_skill_registry())


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="MIA / GODMODE 1000X local employee runtime")
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("status").set_defaults(func=cmd_status)
    a = sub.add_parser("add"); a.add_argument("text"); a.set_defaults(func=cmd_add)
    sub.add_parser("tick").set_defaults(func=cmd_tick)
    sub.add_parser("run-once").set_defaults(func=cmd_run_once)
    l = sub.add_parser("loop"); l.add_argument("--seconds", type=int, default=60); l.set_defaults(func=cmd_loop)
    a = sub.add_parser("approve"); a.add_argument("task_id"); a.set_defaults(func=cmd_approve)
    a = sub.add_parser("complete"); a.add_argument("task_id"); a.set_defaults(func=cmd_complete)
    a = sub.add_parser("log"); a.add_argument("note"); a.set_defaults(func=cmd_log)
    sub.add_parser("character").set_defaults(func=cmd_character)
    sub.add_parser("rights").set_defaults(func=cmd_rights)
    sub.add_parser("score").set_defaults(func=cmd_score)
    sub.add_parser("bonus").set_defaults(func=cmd_bonus)
    sub.add_parser("level-check").set_defaults(func=cmd_level_check)
    sub.add_parser("skills").set_defaults(func=cmd_skills)
    sub.add_parser("sources").set_defaults(func=cmd_sources)
    a = sub.add_parser("route"); a.add_argument("text"); a.set_defaults(func=cmd_route)
    a = sub.add_parser("best"); a.add_argument("text"); a.set_defaults(func=cmd_best)
    a = sub.add_parser("source-plan"); a.add_argument("question"); a.set_defaults(func=cmd_source_plan)
    sub.add_parser("security").set_defaults(func=cmd_security)
    a = sub.add_parser("ethical-check"); a.add_argument("text"); a.set_defaults(func=cmd_ethical_check)
    a = sub.add_parser("threat-model"); a.add_argument("target"); a.set_defaults(func=cmd_threat_model)
    sub.add_parser("secret-scan").set_defaults(func=cmd_secret_scan)
    sub.add_parser("harden-plan").set_defaults(func=cmd_harden_plan)
    sub.add_parser("security-check").set_defaults(func=cmd_security_check)
    return p


def main(argv: List[str] | None = None) -> int:
    ensure_initial_files()
    args = build_parser().parse_args(argv)
    args.func(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
