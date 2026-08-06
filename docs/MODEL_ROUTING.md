# Hermes model routing

Hermes uses deterministic routing with `hybrid` as the default. The selected
model is tried first in hybrid mode; auto mode scores compatible models and
manual mode uses only the selected model unless emergency fallback is enabled.

Model capabilities live in `config/model_capabilities.json`. Privacy and hard
capability requirements filter candidates before scoring. Provider failures are
recorded in `.hermes/provider_cooldowns.json`; cooldowns prevent hot-looping a
failing provider and are cleared automatically after expiry.

The browser controls are persisted locally: routing mode, preferred provider,
emergency fallback, and local-only mode. The API health surfaces expose only
provider/model names, health summaries, and routing state—never keys, prompts,
conversation content, or attachments.

For a request from another client, pass `routing_mode`, `preferred_provider`,
`preferred_model`, `emergency_fallback`, and `local_only` in the runtime
configuration. The original request metadata should be reused for fallback
attempts; tool-producing clients should provide a stable `idempotency_key`.
