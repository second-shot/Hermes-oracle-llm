# LM Studio Local Link Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Persist and enforce Hermes' local LM Studio provider link with clear offline reporting and no automatic cloud fallback.

**Architecture:** Store operator-facing defaults in `config/lm_studio.json` and enforce them through `hermes_provider.py`. Route healthcheck scripts and CLI commands through that resolver so policy remains consistent.

**Tech Stack:** Python standard library, PowerShell, JSON, unittest/pytest-compatible tests.

---

### Task 1: Provider policy and tests

**Files:** Create `tests/test_hermes_provider.py`, `hermes_provider.py`, `config/lm_studio.json`.

- [ ] Write failing tests for loopback recognition, default config, unsafe override rejection, and offline health status.
- [ ] Run `python -m pytest -q tests/test_hermes_provider.py` and confirm failure because the module is absent.
- [ ] Implement the minimal resolver and configuration.
- [ ] Re-run the focused tests and confirm they pass.

### Task 2: CLI integration and operator files

**Files:** Modify `hermes_employee.py`; create `scripts/check_lm_studio.py`, `scripts/check_lm_studio.ps1`, `hermes_refraction.py`, `.env.example`, `docs/LM_STUDIO_LOCAL_LINK.md`; modify `.gitignore`.

- [ ] Add failing CLI assertions to `tests/test_hermes_provider.py`.
- [ ] Run the focused tests and confirm the new assertions fail.
- [ ] Add the provider command and thin CLI wrappers around the resolver.
- [ ] Add the documented environment template, runbook, and exact ignore rules.
- [ ] Re-run focused tests and confirm they pass.

### Task 3: Verification and commit

**Files:** All requested target files.

- [ ] Run the requested healthcheck, provider, status, refraction, compile, focused test, and git-status commands.
- [ ] Confirm no active provider URL points at `api.openai.com` and remote URLs remain gated.
- [ ] Stage only requested files plus the focused regression test and planning records.
- [ ] Commit with `Add LM Studio local provider link and healthcheck`; do not push.
