# Offline Model Router Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route Hermes tasks to the best available loopback-only LM Studio or Ollama model with deterministic offline fallback.

**Architecture:** `hermes_model_router.py` owns provider discovery, normalized model selection, local inference, and decision logging while reusing URL safety from `hermes_provider.py`. `hermes_employee.py` invokes it only after existing approval gates.

**Tech Stack:** Python standard library (`json`, `urllib`, `argparse`), JSON configuration, pytest-compatible tests, PowerShell wrapper.

---

### Task 1: Router policy and model selection

**Files:** Create `tests/test_hermes_model_router.py`, `config/model_router.json`, `hermes_model_router.py`; modify `hermes_provider.py`.

- [ ] Write failing tests for route classification, LM Studio priority, Ollama fallback, size-based selection, vision constraints, and offline fallback.
- [ ] Run `python -m pytest -q tests/test_hermes_model_router.py` and confirm failure because the router module is absent.
- [ ] Implement configuration loading, shared URL validation, provider probes, model normalization, selection, and logging.
- [ ] Re-run the focused tests and confirm they pass.

### Task 2: Local ask and MIA integration

**Files:** Modify `tests/test_hermes_model_router.py`, `hermes_employee.py`, and `hermes_refraction.py` only if a compatible compression helper is required.

- [ ] Add failing tests for deterministic ask fallback and `hermes_employee.py router`.
- [ ] Run the focused tests and confirm the new behavior fails.
- [ ] Implement local-only POST adapters and deterministic response behavior.
- [ ] Add MIA router status and post-approval planning integration without changing safety decisions.
- [ ] Re-run focused and existing provider tests.

### Task 3: Operator assets and verification

**Files:** Create `data/router/model_router_log.json`, `docs/MODEL_ROUTER.md`, and `scripts/check_model_router.ps1`.

- [ ] Add checked-in empty log, runbook, and PowerShell diagnostic.
- [ ] Run all user-requested CLI, compilation, focused test, and status commands.
- [ ] Stage only router-related files and commit `Add offline local model router for Hermes` without pushing.
