# Oracle Types V1

Last updated: 2026-06-21

## OracleEvent

- `id`
- `kind`
- `summary`
- `created_at`
- `mode`
- `risk_level`
- `metadata`

Used for every meaningful action in the V1 pipeline.

## OracleState

- `visualState`
- `heatLevel`
- `urgency`
- `requiresConfirmation`
- `nextBestAction`
- `lastEventSummary`

Resolved from the current events plus confirmation state.

## OracleHeatLevel

- `cold_control`
- `warm_active`
- `pastel_confirm`
- `burning_urgent`
- `liquid_gold_success`

## ConfirmationRequest

- `id`
- `event_id`
- `action_label`
- `reason`
- `risk_level`
- `status`
- `created_at`
- `decided_at`
- `metadata`

## Notification

- `id`
- `kind`
- `title`
- `message`
- `level`
- `created_at`
- `read`
- `metadata`

## ArchitectIntent

- `id`
- `label`
- `confidence`
- `rationale`
- `objective`
- `metadata`

## NextAction

- `id`
- `kind`
- `title`
- `summary`
- `requires_confirmation`
- `metadata`

## UploadRecord

- `id`
- `name`
- `status`
- `created_at`
- `metadata`
