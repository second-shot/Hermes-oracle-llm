# V1 Boundaries

Last updated: 2026-06-21

## Purpose

Oracle V1 Fusion is a strict local-first bridge between the Hermes/MIA Python runtime and the G0DM0D3 web shell.

The goal is not to build the full future platform in one pass. The goal is to ship the operational spine that makes the system feel alive:

- events
- state
- confirmations
- notifications
- intake
- memory visibility
- log visibility
- dual-mode UX

## In Scope

### Runtime ownership

- Hermes/MIA remains the local operational truth.
- G0DM0D3 becomes the Oracle shell.

### Required first-class modes

1. Classic Chat
   - familiar lightweight chat
   - continuity with current web-shell behavior
   - minimal controls in the main flow
   - model/persona controls moved out of the main workflow

2. Architect Mode
   - structured software-architect lane
   - turns chaotic input into objective, intent, events, state, confirmations, next actions, and execution plan suggestions
   - plans and routes before execution

### Required V1 pipeline

`input -> OracleEvent -> OracleState -> ConfirmationRequest (when needed) -> NextAction -> Notification -> Memory / logs`

### Required runtime terms

Only these terms are promoted into runtime code for V1:

- `OracleEvent`
- `OracleState`
- `OracleHeatLevel`
- `ConfirmationRequest`
- `Notification`
- `ArchitectIntent`
- `NextAction`
- `UploadRecord`

### Required backend endpoints

- `GET /api/health`
- `GET /api/oracle/state`
- `GET /api/oracle/events`
- `POST /api/oracle/intake`
- `POST /api/tasks/execute`
- `GET /api/confirmations`
- `POST /api/confirmations/:id/approve`
- `POST /api/confirmations/:id/reject`
- `GET /api/notifications`
- `GET /api/memory`
- `GET /api/logs`

### Required engineering qualities

- local-first
- no provider keys required
- typed
- testable
- modular
- safe incremental steps

## Explicitly Out Of Scope

Do not implement these in Oracle V1:

- reseller workflows
- friends/social
- Supabase migration
- Expo/mobile app
- marketplace posting
- heavy visual polish before the spine works

## Docs-Only Language

The following terms may appear in docs, naming discussions, or roadmap material, but are not V1 runtime objects unless a later milestone proves they are needed:

- Oracle
- Mia
- GoddessMode
- Agent
- Subagent
- Liberty
- Trust
- Heat
- Cold
- Burning Heat
- Dark Cold
- Liquid Gold

## V1 Safety Rules

- Every meaningful action must create an `OracleEvent`.
- Every risky action must create a `ConfirmationRequest`.
- `OracleState` must power both backend logic and frontend presentation.
- Approve/reject actions must update event history, state, notifications, and memory/log visibility.
- The system must still run in a standalone Hermes local mode even if the shell is not launched.

## Integration Boundaries

### Hermes repo

Owns:

- event store
- state resolver
- intake and task execution flow
- confirmation lifecycle
- notifications
- memory/log read models
- adapter interfaces
- local launcher

### G0DM0D3 repo

Owns:

- Classic Chat shell
- Architect Mode shell
- typed Hermes API client
- confirmation cards
- observability panels
- narrow/mobile-usable layout

## Backlog After V1

- V1.5 swipe/review deck
- V2 controlled reseller
- V2.5 Mia/GoddessMode governance
- V3 Supabase/cloud/client expansion
- V4 marketplace automation
- V5 persona-deployed Oracle systems
