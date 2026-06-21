# Oracle V1 Fusion Implementation Plan

**Goal:** Ship a strict V1 local-first Oracle layer where Hermes/MIA is the operational truth and G0DM0D3 becomes the dual-mode shell for Classic Chat plus Architect Mode.

**Architecture:** Add a focused local HTTP spine to the Hermes repo, backed by small typed Oracle V1 records and a state resolver, then connect a minimal typed client and operator UI in the G0DM0D3 repo. Keep the current web shell recognizable, move model/persona complexity out of the main workflow, and avoid cloud dependencies entirely for V1.

**Tech Stack:** Python standard library plus existing Hermes modules, JSON/file-backed local state, Next.js 14, React 18, Zustand, TypeScript.

---

## Audit Summary

- The work spans two repositories:
  - Hermes runtime repo: `C:\Users\max\Hermes-oracle-llm`
  - G0DM0D3 frontend repo: `C:\Users\max\Hermes-oracle-llm\G0DM0D3`
- Hermes already has local task, approval, heartbeat, source, security, and memory/log primitives.
- G0DM0D3 already has a functioning chat shell, a large persisted app store, and a separate Express API built for OpenRouter/HuggingFace workflows.
- Oracle V1 should reuse both codebases but should not reuse the existing hosted/provider-heavy API as its backend spine.
- Baseline environment is not fully installed in the isolated worktrees:
  - Python `pytest` missing
  - frontend `node_modules` missing

## Locked V1 Design

### Backend shape

Create a focused Oracle V1 package in the Hermes repo that owns:

- contracts
- local file-backed store
- state resolver
- intake router
- confirmation lifecycle
- notification lifecycle
- memory/log view models
- HTTP server
- future-facing adapter interfaces

### Frontend shape

Reshape G0DM0D3 into a dual-mode shell:

- Classic Chat remains the default lightweight message surface
- Architect Mode adds structured intake, state, next actions, confirmations, notifications, memory, and logs
- Settings still exist, but model/persona controls are removed from the main workflow emphasis

### Data boundary

Hermes is source of truth. The shell reads and mutates state only through the local Hermes API.

## Planned File Ownership

### Hermes repo additions

- `oracle_v1/__init__.py`
- `oracle_v1/contracts.py`
- `oracle_v1/responses.py`
- `oracle_v1/store.py`
- `oracle_v1/state.py`
- `oracle_v1/intents.py`
- `oracle_v1/service.py`
- `oracle_v1/adapters.py`
- `oracle_v1/http_api.py`
- `scripts/start_oracle_v1.ps1`
- `tests/test_oracle_contracts.py`
- `tests/test_oracle_state.py`
- `tests/test_oracle_api.py`
- `tests/test_oracle_smoke.py`

### Hermes repo likely touch points

- `hermes_employee.py`
- `memory/store.py`
- `scripts/run_smoke_tests.ps1`
- `docs/API_CONTRACTS_V1.md`
- `docs/ORACLE_TYPES_V1.md`

### G0DM0D3 repo additions

- `src/lib/oracle-contracts.ts`
- `src/lib/oracle-client.ts`
- `src/lib/oracle-defaults.ts`
- `src/components/oracle/ModeSwitch.tsx`
- `src/components/oracle/ArchitectPanel.tsx`
- `src/components/oracle/OracleStatePanel.tsx`
- `src/components/oracle/ConfirmationList.tsx`
- `src/components/oracle/NotificationPanel.tsx`
- `src/components/oracle/MemoryLogPanel.tsx`
- `src/components/oracle/ArchitectIntakeForm.tsx`

### G0DM0D3 repo likely touch points

- `src/app/page.tsx`
- `src/components/ChatArea.tsx`
- `src/components/Sidebar.tsx`
- `src/components/SettingsModal.tsx`
- `src/store/index.ts`
- `src/hooks/useApiAutoDetect.ts`

## Execution Order

1. Define and document V1 contracts.
2. Write failing backend tests for:
   - response envelopes
   - Oracle state resolution
   - intake event creation
   - confirmation creation
   - approval/rejection transitions
3. Implement the Hermes local API spine.
4. Add launcher and smoke-test support for local-first runs.
5. Write failing frontend tests or component-level checks where practical, then add:
   - typed client
   - dual-mode shell
   - confirmation UX
   - observability panels
6. Run end-to-end smoke verification across both repos.

## Acceptance Targets

Oracle V1 is done when all of the following are true:

- Hermes/MIA exposes the required local API endpoints.
- No provider key is required for the V1 smoke path.
- Every intake/task/approval/rejection creates an `OracleEvent`.
- Risky actions create `ConfirmationRequest` records.
- `OracleState` drives both API responses and the shell display.
- G0DM0D3 exposes Classic Chat and Architect Mode.
- Architect intake returns structure, not just chat text.
- Notifications, memory, and logs are visible from the shell.
- Hermes standalone local mode still works.

## Known Constraints Before Implementation

- The nested frontend repo must be edited and verified independently from the Hermes repo.
- The live Hermes checkout has mutable runtime artifacts and should remain untouched outside the isolated feature branch/worktree.
- Existing hosted/OpenRouter/HuggingFace code stays available but is not the Oracle V1 dependency path.
