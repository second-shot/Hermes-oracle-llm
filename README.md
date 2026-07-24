# Hermes Oracle

Hermes Oracle is the local-first, approval-gated ecosystem around the Nous Research Hermes runtime. The official runtime stays upgradeable; Oracle, model rotation, memory, safety and workflow modules evolve here through verified Git checkpoints.

## Control plane

Start the local API:

```powershell
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Then open:

```text
http://127.0.0.1:8000/ui
```

The control plane shows:

- Oracle state and consent queue;
- every registered module and its health;
- local model rotation by task;
- zero-cost/default-cloud posture;
- automatic upkeep findings.

Run the same upkeep gate used by GitHub:

```powershell
python scripts/check_ecosystem.py --strict
python -m pytest -q
```

See `docs/ECOSYSTEM_CONTROL_PLANE.md` for architecture and safety boundaries.

## Runtime state

Hermes now stores mutable runtime state outside the repository by default.

## Default location

- Windows: `%LOCALAPPDATA%\Hermes`
- Fallback: `~/.local/share/Hermes`

Runtime subdirectories are:

- `memory/`
- `employee/`
- `security/`
- `sources/`
- `logs/`

## Override

Set `HERMES_DATA_DIR` to use a custom runtime root:

```powershell
$env:HERMES_DATA_DIR = 'C:\temp\hermes-runtime'
python hermes_employee.py status
```

## Migration behavior

- Hermes copies recognized legacy runtime files from the repository into the runtime root on first use.
- Migration is copy-not-move, so repository files remain as a backup.
- Existing destination files win over older repository copies.
- Migration completion is tracked in `migration.json`.

## Recovery

If runtime migration fails:

1. Stop Hermes.
2. Fix the destination directory or permissions.
3. Re-run Hermes.

Legacy repository files remain available because Hermes does not delete them during migration.

## Repository hygiene

- Generated runtime JSON, logs, `.hermes/`, and temporary files are ignored.
- Sanitized fixtures under `tests/fixtures/` remain tracked.
- Legacy tracked runtime files can be removed from version control in a separate reviewed cleanup after migration behavior is verified.
