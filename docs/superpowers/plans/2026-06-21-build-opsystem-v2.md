# Build Opsystem v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the current Hermes/MIA local operator runtime into a clearer, policy-driven Opsystem v2 with stronger state validation, explainable decisions, safer operational commands, and contractor-ready docs/tests.

**Architecture:** Keep the existing standard-library Python CLI as the single runtime entrypoint, but move more behavior behind versioned JSON policies and explicit state schemas. Add decision-trace artifacts and validation commands around the current tick loop so every action stays local, inspectable, approval-gated, and easy to verify from the terminal.

**Tech Stack:** Python 3 standard library, JSON state stores, PowerShell scripts, pytest subprocess smoke tests, markdown docs

---

## File Structure

- Modify: `C:\Users\max\Hermes-oracle-llm\hermes_employee.py` — add policy-backed validation, event tracing, `doctor`, `validate-state`, and `explain-task`.
- Modify: `C:\Users\max\Hermes-oracle-llm\scripts\validate_mia_package.py` — tighten package validation around schemas, commands, and docs.
- Modify: `C:\Users\max\Hermes-oracle-llm\scripts\run_smoke_tests.ps1` — make smoke coverage match the v2 operator flow.
- Modify: `C:\Users\max\Hermes-oracle-llm\scripts\install_employee_task.ps1` — add explicit dry-run, target-path, and backup behavior.
- Modify: `C:\Users\max\Hermes-oracle-llm\tests\test_hermes_employee_cli_v2.py` — expand command coverage and assertions for new commands.
- Modify: `C:\Users\max\Hermes-oracle-llm\tests\test_secret_scan.py` — keep current safety behavior covered while runtime changes land.
- Create: `C:\Users\max\Hermes-oracle-llm\tests\test_validate_state.py` — validate JSON schema/state checks.
- Create: `C:\Users\max\Hermes-oracle-llm\tests\test_explain_task.py` — validate decision-trace output.
- Create: `C:\Users\max\Hermes-oracle-llm\data\employee\events.jsonl` — append-only machine-readable event stream.
- Create: `C:\Users\max\Hermes-oracle-llm\schemas\tasks.schema.json`
- Create: `C:\Users\max\Hermes-oracle-llm\schemas\approvals.schema.json`
- Create: `C:\Users\max\Hermes-oracle-llm\schemas\heartbeat.schema.json`
- Create: `C:\Users\max\Hermes-oracle-llm\schemas\scoreboard.schema.json`
- Create: `C:\Users\max\Hermes-oracle-llm\schemas\source_registry.schema.json`
- Create: `C:\Users\max\Hermes-oracle-llm\schemas\event.schema.json`
- Create: `C:\Users\max\Hermes-oracle-llm\docs\MIA_OPERATOR_ACCEPTANCE.md`
- Create: `C:\Users\max\Hermes-oracle-llm\docs\MIA_OPERATOR_BACKLOG.md`
- Create: `C:\Users\max\Hermes-oracle-llm\docs\adr\ADR-001-local-first-runtime.md`
- Create: `C:\Users\max\Hermes-oracle-llm\docs\adr\ADR-002-json-state.md`
- Create: `C:\Users\max\Hermes-oracle-llm\docs\adr\ADR-003-approval-gates.md`
- Create: `C:\Users\max\Hermes-oracle-llm\docs\adr\ADR-004-no-network-default.md`

### Task 1: Lock the v2 state contract

**Files:**
- Create: `C:\Users\max\Hermes-oracle-llm\schemas\tasks.schema.json`
- Create: `C:\Users\max\Hermes-oracle-llm\schemas\approvals.schema.json`
- Create: `C:\Users\max\Hermes-oracle-llm\schemas\heartbeat.schema.json`
- Create: `C:\Users\max\Hermes-oracle-llm\schemas\scoreboard.schema.json`
- Create: `C:\Users\max\Hermes-oracle-llm\schemas\source_registry.schema.json`
- Create: `C:\Users\max\Hermes-oracle-llm\schemas\event.schema.json`
- Modify: `C:\Users\max\Hermes-oracle-llm\scripts\validate_mia_package.py`
- Test: `C:\Users\max\Hermes-oracle-llm\tests\test_validate_state.py`

- [ ] **Step 1: Write the failing state-validation tests**

```python
from pathlib import Path
import json

import hermes_employee as he


def test_validate_state_accepts_default_repo_state(tmp_path, monkeypatch):
    monkeypatch.setattr(he, "ROOT", tmp_path)
    he.ensure_files()
    result = he.validate_state_files()
    assert result["ok"] is True
    assert result["errors"] == []


def test_validate_state_rejects_task_missing_required_field(tmp_path, monkeypatch):
    monkeypatch.setattr(he, "ROOT", tmp_path)
    he.ensure_files()
    tasks_path = tmp_path / "data" / "employee" / "tasks.json"
    tasks_path.write_text(json.dumps([{"id": "T-1"}]), encoding="utf-8")
    result = he.validate_state_files()
    assert result["ok"] is False
    assert any("tasks.json" in err for err in result["errors"])
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `pytest C:\Users\max\Hermes-oracle-llm\tests\test_validate_state.py -v`

Expected: FAIL because `validate_state_files()` and the schema-backed checks do not exist yet.

- [ ] **Step 3: Add minimal schema files and validator wiring**

```python
STATE_REQUIRED_TASK_KEYS = {
    "id", "text", "status", "priority", "risk", "created_at", "updated_at", "proposal", "result"
}


def validate_task_record(task: dict[str, object]) -> list[str]:
    missing = sorted(STATE_REQUIRED_TASK_KEYS - set(task))
    return [f"tasks.json missing keys for task {task.get('id', '<unknown>')}: {', '.join(missing)}"] if missing else []


def validate_state_files() -> dict[str, object]:
    ensure_files()
    errors: list[str] = []
    for task in load_json(TASKS):
        errors.extend(validate_task_record(task))
    return {"ok": not errors, "errors": errors}
```

```python
REQUIRED_FILES += [
    "schemas/tasks.schema.json",
    "schemas/approvals.schema.json",
    "schemas/heartbeat.schema.json",
    "schemas/scoreboard.schema.json",
    "schemas/source_registry.schema.json",
    "schemas/event.schema.json",
]
```

- [ ] **Step 4: Run tests and validator to verify they pass**

Run: `pytest C:\Users\max\Hermes-oracle-llm\tests\test_validate_state.py -v`

Expected: PASS

Run: `python C:\Users\max\Hermes-oracle-llm\scripts\validate_mia_package.py C:\Users\max\Hermes-oracle-llm`

Expected: `MIA package validation passed.`

- [ ] **Step 5: Commit the state-contract slice**

```bash
git -C C:\Users\max\Hermes-oracle-llm add schemas scripts/validate_mia_package.py tests/test_validate_state.py hermes_employee.py
git -C C:\Users\max\Hermes-oracle-llm commit -m "feat: add opsystem v2 state validation"
```

### Task 2: Make tick decisions explainable and machine-readable

**Files:**
- Modify: `C:\Users\max\Hermes-oracle-llm\hermes_employee.py`
- Create: `C:\Users\max\Hermes-oracle-llm\data\employee\events.jsonl`
- Create: `C:\Users\max\Hermes-oracle-llm\tests\test_explain_task.py`
- Test: `C:\Users\max\Hermes-oracle-llm\tests\test_hermes_employee_cli_v2.py`

- [ ] **Step 1: Write the failing explainability tests**

```python
import json
import subprocess
import sys


def test_explain_task_shows_risk_and_next_step():
    add_result = subprocess.run(
        [sys.executable, "hermes_employee.py", "add", "Inspect repo hardening and prepare a safe commit plan"],
        capture_output=True,
        text=True,
        check=True,
    )
    task_id = add_result.stdout.strip().split()[-1]
    subprocess.run([sys.executable, "hermes_employee.py", "tick"], capture_output=True, text=True, check=True)
    explain = subprocess.run([sys.executable, "hermes_employee.py", "explain-task", task_id], capture_output=True, text=True)
    assert explain.returncode == 0
    assert "risk: medium" in explain.stdout.lower()
    assert "approval" in explain.stdout.lower()
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run: `pytest C:\Users\max\Hermes-oracle-llm\tests\test_explain_task.py -v`

Expected: FAIL because `explain-task` and persisted decision traces do not exist yet.

- [ ] **Step 3: Add event logging and explanation plumbing**

```python
EVENTS = ROOT / "data" / "employee" / "events.jsonl"


def append_event(event_type: str, payload: dict[str, object]) -> None:
    EVENTS.parent.mkdir(parents=True, exist_ok=True)
    entry = {"timestamp": now(), "type": event_type, **payload}
    with EVENTS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def render_task_explanation(task: dict[str, object]) -> str:
    return (
        f"task: {task['id']}\n"
        f"status: {task['status']}\n"
        f"risk: {task['risk']}\n"
        f"proposal: {task.get('proposal', '')}\n"
        f"result: {task.get('result', '')}\n"
    )
```

```python
def cmd_explain_task(args: argparse.Namespace) -> None:
    tasks = load_json(TASKS)
    for task in tasks:
        if task.get("id") == args.task_id:
            print(render_task_explanation(task))
            return
    raise SystemExit(f"Task not found: {args.task_id}")
```

- [ ] **Step 4: Run the CLI smoke tests to verify the new path passes**

Run: `pytest C:\Users\max\Hermes-oracle-llm\tests\test_explain_task.py C:\Users\max\Hermes-oracle-llm\tests\test_hermes_employee_cli_v2.py -v`

Expected: PASS

- [ ] **Step 5: Commit the explainability slice**

```bash
git -C C:\Users\max\Hermes-oracle-llm add hermes_employee.py data/employee/events.jsonl tests/test_explain_task.py tests/test_hermes_employee_cli_v2.py
git -C C:\Users\max\Hermes-oracle-llm commit -m "feat: add opsystem v2 task explainability"
```

### Task 3: Add `validate-state` and `doctor` as operator maintenance commands

**Files:**
- Modify: `C:\Users\max\Hermes-oracle-llm\hermes_employee.py`
- Modify: `C:\Users\max\Hermes-oracle-llm\tests\test_hermes_employee_cli_v2.py`
- Modify: `C:\Users\max\Hermes-oracle-llm\scripts\run_smoke_tests.ps1`
- Test: `C:\Users\max\Hermes-oracle-llm\tests\test_validate_state.py`

- [ ] **Step 1: Extend the CLI smoke test with the new commands**

```python
COMMANDS = [
    ["status"],
    ["character"],
    ["security"],
    ["rights"],
    ["skills"],
    ["sources"],
    ["ethical-check", "status check"],
    ["source-plan", "build local bridge"],
    ["security-check", "build local bridge"],
    ["decide", "build local bridge"],
    ["tick", "status check"],
    ["validate"],
    ["validate-state"],
    ["doctor"],
]
```

- [ ] **Step 2: Run smoke coverage to verify it fails before implementation**

Run: `pytest C:\Users\max\Hermes-oracle-llm\tests\test_hermes_employee_cli_v2.py -v`

Expected: FAIL because `doctor` is not registered yet.

- [ ] **Step 3: Implement the minimal maintenance commands**

```python
def cmd_validate_state(_: argparse.Namespace) -> None:
    result = validate_state_files()
    if not result["ok"]:
        raise SystemExit("\n".join(result["errors"]))
    print("STATE VALID")


def cmd_doctor(_: argparse.Namespace) -> None:
    result = validate_state_files()
    print(f"python: {sys.version.split()[0]}")
    print(f"state_ok: {result['ok']}")
    print(f"root: {ROOT}")
    if not result["ok"]:
        raise SystemExit(1)
```

```python
sub.add_parser("doctor").set_defaults(func=cmd_doctor)
sub.add_parser("validate-state").set_defaults(func=cmd_validate_state)
```

```powershell
python .\hermes_employee.py validate-state
python .\hermes_employee.py doctor
```

- [ ] **Step 4: Re-run CLI and smoke verification**

Run: `pytest C:\Users\max\Hermes-oracle-llm\tests\test_hermes_employee_cli_v2.py C:\Users\max\Hermes-oracle-llm\tests\test_validate_state.py -v`

Expected: PASS

Run: `powershell -ExecutionPolicy Bypass -File C:\Users\max\Hermes-oracle-llm\scripts\run_smoke_tests.ps1`

Expected: script completes and prints the v2 smoke-test completion banner.

- [ ] **Step 5: Commit the maintenance-command slice**

```bash
git -C C:\Users\max\Hermes-oracle-llm add hermes_employee.py scripts/run_smoke_tests.ps1 tests/test_hermes_employee_cli_v2.py tests/test_validate_state.py
git -C C:\Users\max\Hermes-oracle-llm commit -m "feat: add opsystem v2 maintenance commands"
```

### Task 4: Harden installation and validation for contractor use

**Files:**
- Modify: `C:\Users\max\Hermes-oracle-llm\scripts\install_employee_task.ps1`
- Modify: `C:\Users\max\Hermes-oracle-llm\scripts\validate_mia_package.py`
- Modify: `C:\Users\max\Hermes-oracle-llm\docs\MIA_OPERATOR_RUNBOOK.md`
- Create: `C:\Users\max\Hermes-oracle-llm\docs\MIA_OPERATOR_ACCEPTANCE.md`

- [ ] **Step 1: Write the failing acceptance expectations into docs and tests**

```markdown
## Installer acceptance

- `install_employee_task.ps1 -DryRun` makes no filesystem changes.
- `install_employee_task.ps1 -Repo <path>` targets only the selected repo.
- Existing scheduled-task files are backed up before replacement.
- Validation and smoke commands are printed before the operator is told to commit.
```

```python
assert "DryRun" in install_script_text
assert "Repo" in install_script_text
assert "backup" in install_script_text.lower()
```

- [ ] **Step 2: Run validation checks to capture the current gap**

Run: `python C:\Users\max\Hermes-oracle-llm\scripts\validate_mia_package.py C:\Users\max\Hermes-oracle-llm`

Expected: FAIL after the new acceptance assertions are added and before the installer is updated.

- [ ] **Step 3: Implement the safer installer flow**

```powershell
param(
  [string]$Repo = "C:\Users\max\Hermes-oracle-llm",
  [switch]$DryRun
)

$target = Resolve-Path $Repo
$backupRoot = Join-Path $target ".backup\mia-installer"

if ($DryRun) {
  Write-Host "[DRY RUN] Would validate repo at $target"
  Write-Host "[DRY RUN] Would back up scheduled-task artifacts into $backupRoot"
  exit 0
}
```

```markdown
## Pre-commit checklist

1. `python .\scripts\validate_mia_package.py .`
2. `python .\hermes_employee.py validate-state`
3. `python .\hermes_employee.py doctor`
4. `python .\hermes_employee.py secret-scan`
5. Review `git status --short`
```

- [ ] **Step 4: Run installer/validator verification**

Run: `powershell -ExecutionPolicy Bypass -File C:\Users\max\Hermes-oracle-llm\scripts\install_employee_task.ps1 -DryRun -Repo C:\Users\max\Hermes-oracle-llm`

Expected: prints dry-run actions only, exits 0

Run: `python C:\Users\max\Hermes-oracle-llm\scripts\validate_mia_package.py C:\Users\max\Hermes-oracle-llm`

Expected: `MIA package validation passed.`

- [ ] **Step 5: Commit the contractor-ops slice**

```bash
git -C C:\Users\max\Hermes-oracle-llm add scripts/install_employee_task.ps1 scripts/validate_mia_package.py docs/MIA_OPERATOR_RUNBOOK.md docs/MIA_OPERATOR_ACCEPTANCE.md
git -C C:\Users\max\Hermes-oracle-llm commit -m "feat: harden opsystem v2 installer and acceptance docs"
```

### Task 5: Publish the v2 operating docs, ADRs, and backlog

**Files:**
- Create: `C:\Users\max\Hermes-oracle-llm\docs\MIA_OPERATOR_BACKLOG.md`
- Create: `C:\Users\max\Hermes-oracle-llm\docs\adr\ADR-001-local-first-runtime.md`
- Create: `C:\Users\max\Hermes-oracle-llm\docs\adr\ADR-002-json-state.md`
- Create: `C:\Users\max\Hermes-oracle-llm\docs\adr\ADR-003-approval-gates.md`
- Create: `C:\Users\max\Hermes-oracle-llm\docs\adr\ADR-004-no-network-default.md`
- Modify: `C:\Users\max\Hermes-oracle-llm\docs\SPEC-001-MIA-Local-Operator-Runtime.md`

- [ ] **Step 1: Draft the failing documentation checklist**

```markdown
- backlog includes milestone, owner, acceptance criteria, and evidence field for each slice
- ADR set explains why local-first, JSON state, approval gates, and no-network default are required
- runtime spec links directly to acceptance doc, backlog, and ADR directory
```

- [ ] **Step 2: Review docs manually to confirm the checklist is not fully satisfied yet**

Run: `rg -n "ADR-|acceptance|backlog" C:\Users\max\Hermes-oracle-llm\docs`

Expected: partial or missing results for the new artifacts.

- [ ] **Step 3: Write the minimal v2 operating docs**

```markdown
# MIA Operator Backlog

| Milestone | Slice | Owner | Acceptance Criteria | Evidence |
| --- | --- | --- | --- | --- |
| M1 | Safe install and validation | Contractor | Dry-run installer, validator, smoke script all pass | command transcript |
| M2 | Policy-backed runtime | Contractor | risk/approval/source rules loaded from JSON and validated | pytest + CLI output |
| M3 | Explainability | Contractor | `explain-task` and `events.jsonl` show why a task moved state | sample task transcript |
```

```markdown
# ADR-001: Local-first runtime

## Status
Accepted

## Decision
The runtime executes locally by default and treats any network use as a separate approval-gated project.

## Consequences
- predictable operator behavior
- lower cost
- easier auditing
```

- [ ] **Step 4: Verify docs presence and linkage**

Run: `rg -n "MIA Operator Backlog|ADR-001|MIA_OPERATOR_ACCEPTANCE" C:\Users\max\Hermes-oracle-llm\docs`

Expected: matches in the new files and spec cross-links.

- [ ] **Step 5: Commit the documentation slice**

```bash
git -C C:\Users\max\Hermes-oracle-llm add docs/MIA_OPERATOR_BACKLOG.md docs/adr docs/SPEC-001-MIA-Local-Operator-Runtime.md
git -C C:\Users\max\Hermes-oracle-llm commit -m "docs: publish opsystem v2 operating guidance"
```

## Final verification

- [ ] Run: `pytest C:\Users\max\Hermes-oracle-llm\tests -v`
- [ ] Run: `python C:\Users\max\Hermes-oracle-llm\scripts\validate_mia_package.py C:\Users\max\Hermes-oracle-llm`
- [ ] Run: `powershell -ExecutionPolicy Bypass -File C:\Users\max\Hermes-oracle-llm\scripts\run_smoke_tests.ps1`
- [ ] Run: `python C:\Users\max\Hermes-oracle-llm\hermes_employee.py secret-scan`
- [ ] Review: `git -C C:\Users\max\Hermes-oracle-llm status --short`

Expected final state:

- pytest passes
- package validator passes
- smoke script passes
- secret scan produces a masked report
- repo diff is limited to the planned v2 files above

## Self-review

- Spec coverage: the plan covers the current runtime spec’s missing pieces around schemas, safer install, explainability, acceptance coverage, backlog, and ADRs.
- Placeholder scan: no `TODO`, `TBD`, or “implement later” placeholders remain in the task steps.
- Type consistency: the plan uses one naming set throughout — `validate_state_files()`, `cmd_validate_state`, `cmd_doctor`, `cmd_explain_task`, and `events.jsonl`.
