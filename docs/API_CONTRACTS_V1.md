# API Contracts V1

Last updated: 2026-06-21

## Response Envelope

### Success

```json
{
  "status": "ok",
  "data": {},
  "meta": {}
}
```

### Failure

```json
{
  "status": "error",
  "error": {
    "code": "string",
    "message": "string"
  },
  "details": {}
}
```

## Local Endpoints

### GET `/api/health`

- Returns local runtime availability and operator mode.

### GET `/api/oracle/state`

- Returns the resolved `OracleState` used by both backend logic and the UI.

### GET `/api/oracle/events`

- Returns recent `OracleEvent` records in source-of-truth order.

### POST `/api/oracle/intake`

- Accepts:
  - `mode`
  - `text`
  - `objective`
  - `task`
  - `upload`
  - `metadata`
- Returns:
  - created `OracleEvent`
  - optional `ArchitectIntent`
  - suggested `NextAction`
  - `requiresConfirmation`
  - optional `ConfirmationRequest`
  - current `OracleState`

### POST `/api/tasks/execute`

- Accepts a task/objective payload for safe local execution or approval gating.
- Always creates an `OracleEvent`.
- Creates a `ConfirmationRequest` when risk is medium/high.

### GET `/api/confirmations`

- Returns all current `ConfirmationRequest` records.

### POST `/api/confirmations/:id/approve`

- Approves a pending confirmation.
- Creates an approval event.
- Updates notifications, memory, and logs.

### POST `/api/confirmations/:id/reject`

- Rejects a pending confirmation.
- Creates a rejection event.
- Updates notifications, memory, and logs.

### GET `/api/notifications`

- Returns recent operator-facing `Notification` records.

### GET `/api/memory`

- Returns structured Oracle V1 memory plus any persisted local memory state.

### GET `/api/logs`

- Returns structured activity log entries plus raw markdown log content.
