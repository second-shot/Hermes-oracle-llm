# Hermes Oracle Ecosystem Control Plane

## Boundary

The official Nous Research Hermes application remains an upgradeable runtime. This repository is the governed local-first ecosystem around it.

The control plane does not:

- modify the installed Nous core;
- post to marketplaces or messaging platforms;
- unlock cloud inference automatically;
- promote an incubating module without contracts and tests;
- rewrite its own safety policy.

## Runtime loop

1. Capture the operator direction.
2. Compress and classify it.
3. Consult cache and project memory.
4. Select the smallest suitable local model.
5. Request confirmation for risky or external actions.
6. Execute one bounded checkpoint.
7. Verify and record evidence.
8. Return the next action to Oracle.

## Control-plane API

Run:

```powershell
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open:

```text
http://127.0.0.1:8000/ui
```

Key endpoints:

- `GET /api/ecosystem` — module registry, cost posture, rotation matrix and upkeep report.
- `GET /api/oracle/state` — current Oracle state and next action.
- `POST /api/oracle/intake` — record a direction and apply the confirmation boundary.
- `GET /api/confirmations` — pending operator decisions.
- `POST /api/confirmations/{id}/approve` — approve one local action.
- `POST /api/confirmations/{id}/reject` — reject one action.

## Module contract

Every module is declared in `config/ecosystem.modules.json`.

An active module must have:

- one stable entrypoint;
- required implementation files;
- a stated upkeep cadence;
- tests covering its contract.

`python scripts/check_ecosystem.py --strict` fails when an active module loses a required seam.

## Cost boundary

`config.json` defaults to stub/local mode. Model rotation is configured in `config/hermes.model.rotation.yaml`.

- LM Studio is first.
- llama.cpp is second.
- MLX remains available on Apple Silicon.
- OpenAI and OpenRouter are declared bridges, not fallbacks.
- The exact one-task unlock mechanism is retained.
- Paid models remain disabled by policy.

## Automatic upkeep

`.github/workflows/hermes-upkeep.yml` runs on pull requests, pushes to `main`, manual dispatch and a weekly schedule. It:

1. installs declared dependencies;
2. runs the full test suite;
3. runs the strict ecosystem audit;
4. uploads the report as a short-lived GitHub artifact.

It reports drift. It does not rewrite modules or merge changes.
