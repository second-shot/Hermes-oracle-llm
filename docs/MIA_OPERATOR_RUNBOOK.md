# MIA Operator Runbook

## 1. First local validation

```powershell
cd C:\Users\max\Hermes-oracle-llm
python hermes_employee.py status
python hermes_employee.py character
python hermes_employee.py rights
python hermes_employee.py skills
python hermes_employee.py sources
python hermes_employee.py security
```

Expected result: all commands print local status/docs. No cloud login, Copilot, paid API, or network is required.

## 2. Add a low-risk task

```powershell
python hermes_employee.py add "Summarize the local MIA docs and propose one safe next build step"
python hermes_employee.py tick
python hermes_employee.py status
```

Expected result: low-risk task completes or produces a local planning checkpoint.

## 3. Add a medium-risk task

```powershell
python hermes_employee.py add "Inspect repo hardening and prepare a safe commit plan"
python hermes_employee.py tick
type .\data\employee\approvals.json
```

Expected result: proposal is created. No risky edit is executed silently.

## 4. Approval flow

```powershell
python hermes_employee.py approve T-YYYYMMDD-HHMMSS
python hermes_employee.py tick
```

Expected result: approved medium-risk task can proceed to a safe checkpoint.

## 5. Defensive security check

```powershell
python hermes_employee.py secret-scan
python hermes_employee.py threat-model "Hermes local repo"
python hermes_employee.py harden-plan
python hermes_employee.py security-check
```

Expected result: reports are written to `data/security`. Secrets are masked. No files are edited or deleted.

## 6. Before commit

```powershell
python .\scripts\validate_mia_package.py .
python hermes_employee.py security-check
git status --short
```

Commit only after reviewing generated reports.

## 7. Safe operating rules

- Keep MIA foreground-visible unless a scheduled task is explicitly reviewed.
- Do not approve vague high-risk tasks.
- Do not store real secrets in JSON task text, logs, approvals, or docs.
- Run `secret-scan` before every push.
- Treat network use as a separate approved project, not an MVP default.
