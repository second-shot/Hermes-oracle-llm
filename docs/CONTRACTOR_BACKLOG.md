# Contractor Backlog

## M1 — Safe Overlay Install

### Task M1.1: Add safe installer

Implement `scripts/SAFE_INSTALL_OVERLAY.ps1` with:

- `-Repo` parameter
- `-DryRun` mode
- backup folder creation
- no delete operations
- copy overlay files only

Acceptance:

- Dry-run lists files without copying.
- Real run copies docs/policies/schemas/scripts.
- Existing files are backed up before overwrite.

### Task M1.2: Add package validator

Implement `scripts/validate_mia_package.py`.

Acceptance:

- validates required files exist
- validates JSON files parse
- compiles `hermes_employee.py`
- checks important CLI command names appear in parser source
- exits non-zero on failure

## M2 — Policy Externalization

### Task M2.1: Move risk keywords to policy JSON

Acceptance:

- high/medium keyword lists are read from `policies/risk_policy.json`
- existing classifications remain compatible
- missing policy file falls back safely to stricter behavior

### Task M2.2: Add approval policy loader

Acceptance:

- approval policy is read from `policies/approval_policy.json`
- medium/high risk rules are not bypassable through task wording
- unsafe security is refused before general approval logic

## M3 — State Validation

### Task M3.1: Add `validate-state` command

Acceptance:

- reads local JSON stores
- reports missing/invalid fields
- never edits state unless `--repair` is explicitly provided
- `--repair` must backup before writing

### Task M3.2: Add event JSONL

Acceptance:

- each tick emits one event into `data/employee/events.jsonl`
- event includes timestamp, task id, risk, decision, and result
- markdown logs remain for human reading

## M4 — Explainability

### Task M4.1: Add decision trace

Acceptance:

- each task records `risk_reason`, `route_reason`, and `approval_reason`
- `explain-task <id>` prints the decision trace
- high-risk task trace clearly says why it did not execute

## M5 — QA and Release

### Task M5.1: Smoke test script

Acceptance:

- runs status, character, security, source plan, ethical checks, and compile
- no network calls
- exits non-zero on failure

### Task M5.2: Release checklist

Acceptance:

- README updated
- SPEC updated
- security check clean or findings documented
- git status reviewed manually
