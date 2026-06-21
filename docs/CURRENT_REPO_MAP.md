# Current Repo Map

Last audited: 2026-06-21

## Repo Topology

The current product is split across two repositories:

1. `C:\Users\max\Hermes-oracle-llm`
   - Primary Hermes/MIA local runtime repo.
   - Git branch in live checkout: `local-build`.
   - Isolated feature worktree used for V1 Fusion: `C:\Users\max\.config\superpowers\worktrees\Hermes-oracle-llm\oracle-v1-fusion` on `codex/oracle-v1-fusion`.

2. `C:\Users\max\Hermes-oracle-llm\G0DM0D3`
   - Separate Git repository nested inside the Hermes repo.
   - Root repo tracks it as a gitlink-like entry (`160000`) but `.gitmodules` is missing, so it behaves as a standalone nested repo rather than a healthy configured submodule.
   - Live branch: `main`.
   - Isolated feature worktree used for V1 Fusion: `C:\Users\max\.config\superpowers\worktrees\G0DM0D3\oracle-v1-fusion` on `codex/oracle-v1-fusion`.

## Hermes / MIA Runtime Repo

### Entry points

- `hermes_employee.py`
  - Current local-first operational CLI.
  - Owns task creation, approvals, heartbeat, scoreboards, source planning, security checks, logs, and validation.
- `main.py`
  - Separate interactive runner that routes to `core.executor.execute_task`.
  - Not suited for non-interactive smoke runs because it immediately enters `input()` when no command is passed.
- `scripts/start_employee.ps1`
  - Launches `python hermes_employee.py loop`.
- `scripts/run_smoke_tests.ps1`
  - Runs the current CLI commands in sequence.

### Current runtime/data structure

- `core/executor.py`
  - Compresses input, routes tasks, calls provider logic, updates memory, and caches responses.
- `llm/client.py`
  - Stub-first provider adapter with optional OpenAI integration.
- `memory/store.py`
  - Stores structured memory in `memory/structured.json` and appends session logs to `memory/logs.md`.
- `data/employee/*`
  - Tasks, approvals, heartbeat, scoreboards, and employee log.
- `data/security/*`
  - Security report/log/scoreboard and secret scan output.
- `data/sources/*`
  - Source registry, plan log, and cache.

### API/runtime status before V1 Fusion

- No local HTTP API exists yet for Oracle V1.
- Existing backend modules under `backend/` are helper services and connectors, not a running HTTP spine for the local operator workflow.
- Existing terminology in code is broader than V1 and mixes MIA/GODMODE language with task/runtime logic.

### Existing tests

- `tests/test_hermes_employee_cli_v2.py`
- `tests/test_secret_scan.py`
- other backend/model policy tests under `tests/`

### Current baseline findings

- `python hermes_employee.py validate` passes.
- `python -m pytest tests\test_hermes_employee_cli_v2.py -q` fails because `pytest` is not installed in the current Python environment.
- `python -m pytest tests\test_secret_scan.py -q` fails for the same reason.
- Live repo has runtime-generated modified files:
  - `data/employee/heartbeat.json`
  - `data/employee/log.md`
  - `data/employee/scoreboard.json`
  - `data/security/secret_scan_report.md`
  - `data/security/security_log.md`
  - `data/security/security_report.md`
  - `data/security/security_scoreboard.json`
  - `data/sources/source_log.json`
  - untracked `memory/logs.md`
- Those files should be treated as operational artifacts, not refactor targets.

### Current env/config surface

- `config.json`
  - Defaults `cloud_enabled` to `true` and `llm.provider` to `openai`, even though local stub mode is the safe no-key path.
- `llm/client.py`
  - Reads `OPENAI_API_KEY`, `HERMES_OPENAI_API_KEY`, and `.env`.
- `requirements.txt`
  - Declares `openai`, `python-dotenv`, and `pytest`.

## G0DM0D3 Frontend Repo

### App structure

- `src/app/page.tsx`
  - Top-level shell for the current chat app.
- `src/components/ChatArea.tsx`
  - Current chat surface.
- `src/components/Sidebar.tsx`
  - Conversation navigation.
- `src/components/SettingsModal.tsx`
  - Large settings surface for API keys, prompts, ULTRAPLINIAN, CONSORTIUM, memory, privacy, and data.
- `src/store/index.ts`
  - Single large Zustand store holding chat, settings, memory, streaming, API, and model/persona state.

### Current routing/UI behavior

- Single route app rooted at `src/app/page.tsx`.
- Current UX is chat-first.
- Model and persona concerns are prominent in the main app state and settings.
- Current stored chat history is browser-local via Zustand persistence.

### Existing API/client code

- `src/lib/openrouter.ts`
  - Browser client for direct OpenRouter calls and the current self-hosted API proxy mode.
- `src/hooks/useApiAutoDetect.ts`
  - Detects a same-origin `/v1/health` + `/v1/tier` API and auto-enables proxy mode.
- `api/server.ts`
  - Express server for ULTRAPLINIAN/CONSORTIUM/OpenRouter workflows.
  - Not compatible with the strict local-first Oracle V1 requirement because it is built around provider keys, OpenRouter, HuggingFace, and hosted research flows.

### Frontend env surface

- `PORT`
- `CORS_ORIGIN`
- `OPENROUTER_API_KEY`
- `GODMODE_API_KEY`
- `GODMODE_API_KEYS`
- `GODMODE_TIER_KEYS`
- `RATE_LIMIT_TOTAL`
- `RATE_LIMIT_PER_MINUTE`
- `RATE_LIMIT_PER_DAY`
- `HF_TOKEN`
- `HF_DATASET_REPO`
- `HF_DATASET_BRANCH`
- `HF_FLUSH_THRESHOLD`
- `HF_FLUSH_INTERVAL_MS`
- `HF_SPACE_URL`

### Current baseline findings

- `npm run lint` fails because `node_modules` is not installed in the isolated worktree.
- The repo is otherwise clean before V1 Fusion changes.

## Shared Boundary Findings

### Best place for shared V1 contracts

Because the repos are split, the safest V1 boundary is:

- Hermes repo:
  - Python source-of-truth contracts in a new focused package for the Oracle V1 API/runtime.
- G0DM0D3 repo:
  - Matching TypeScript contract definitions and a small typed client for the Hermes local API.
- Docs:
  - Canonical contract docs stay in the Hermes repo `docs/` directory because that repo is the operational truth and already owns the runtime behavior.

### Recommended V1 implementation seams

- Hermes repo owns:
  - Oracle events
  - Oracle state resolver
  - confirmations
  - notifications
  - intake
  - local memory/log read models
  - adapter interfaces
  - launcher
- G0DM0D3 repo owns:
  - dual-mode shell
  - typed API client
  - local polling/refresh UX
  - Classic Chat continuity layer
  - Architect Mode operator surfaces

## Current Risks To Preserve

- Do not overwrite runtime data files in the live `local-build` checkout.
- Do not depend on OpenRouter or cloud keys for Oracle V1.
- Do not treat the existing `api/server.ts` as the V1 backend spine; it solves a different product.
- Do not couple V1 contracts to reseller, social, Supabase, Expo, or marketplace concepts.
