# Security Check

Created: 2026-06-20T19:13:27

Question: build local bridge

## Secret Scan
Findings: 0

## Hardening Plan
# Hermes Hardening Plan

Created: 2026-06-20T19:13:27

## Checks
- .gitignore exists: True
- risky root files detected: none

## Recommended Safe Actions
1. Keep `.env`, keys, cache, logs, virtual environments, and pycache ignored.
2. Keep task/security JSON state tracked unless it contains secrets.
3. Run `python hermes_employee.py secret-scan` before every push.
4. Require approval before git push, network use, dependency install, or file moves.
5. Keep MIA tick-based, visible, and reversible.

No files were edited by this plan.

