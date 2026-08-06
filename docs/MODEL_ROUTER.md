# Hermes Model Router

Hermes now keeps one deterministic fallback chain per request so the application does not stop when a provider runs out of credits or becomes temporarily unavailable.

## Request flow

1. Refraction normalizes and bounds task text.
2. MIA classifies risk and enforces existing approval gates.
3. `backend.services.model_router.ModelRouter` classifies safe or approved work as `simple_chat`, `architecture_plan`, `repo_debug`, `code_patch`, `screenshot_or_image`, or `summarise_memory`.
4. Hermes replays the same prompt, memory snapshot, and repo index across the provider chain in this order:
   - the currently configured primary cloud provider from `config.json`
   - each configured OpenRouter free model from `config/hermes.model.rotation.yaml`
   - local Ollama `qwen2.5:3b`
   - local Ollama `llama3.2:3b`
5. The router writes a sanitized audit record with provider, model, failure reason, fallback decision, and latency.
6. When a fallback succeeds, Hermes surfaces a concise fallback notice without exposing prompt contents or secrets.

Compression happens before model selection so repeated whitespace and oversized raw task text do not waste context. Risk checks still use the original task, and compression never grants permission or bypasses approval.

## Provider handling

- Retryable failures trigger the next provider immediately:
  - HTTP `402`
  - HTTP `429`
  - insufficient credits
  - exhausted quota
  - provider unavailable
  - model unavailable
  - connection failure
  - timeout
- Authentication failures are not retried indefinitely. Hermes records the failure, applies a short cooldown, and moves on.
- Active provider cooldowns temporarily disable semantic cache reuse so Hermes does not replay stale answers while a provider is degraded.
- Audit logs live at `.hermes/logs/model_router_audit.json`.
- Cooldown state lives at `.hermes/provider_cooldowns.json`.

## Local endpoints

- Primary API health: `/health`
- Primary API status: `/api/status`
- LM Studio primary: `http://127.0.0.1:1234/v1`
- LM Studio fallback: `http://localhost:1234/v1`
- Ollama native: `http://127.0.0.1:11434/api`
- Ollama OpenAI-compatible: `http://127.0.0.1:11434/v1`

Remote URLs are refused unless explicitly allowlisted. `api.openai.com` remains blocked when `cloud_enabled` is false. OpenRouter free fallback is only considered when cloud routing is enabled for the active request.

Provider HTTP requests ignore ambient proxy settings and refuse redirects, keeping prompts and the optional LM Studio token on the validated endpoint.

## Configuration

`config/hermes.model.rotation.yaml` now owns the deterministic fallback settings:

```yaml
fallback:
  openrouter_free_models:
    - "openrouter/free-model-only"
  ollama_models:
    - "qwen2.5:3b"
    - "llama3.2:3b"
  temporary_failure_cooldown_seconds: 300
  authentication_failure_cooldown_seconds: 300
```

`config.json` still owns the active primary cloud provider and model:

```json
{
  "cloud_enabled": true,
  "llm": {
    "provider": "openai",
    "model": "gpt-4o-mini"
  }
}
```

When all cloud providers fail, Hermes prefers local Ollama and keeps the same prompt and context for the fallback attempt.

## Local runtime setup

Open LM Studio, load a model, open its Developer or Local Server view, select port `1234`, and start the server.

Install and start Ollama locally, then pull the fallback models:

```powershell
ollama serve
ollama pull qwen2.5:3b
ollama pull llama3.2:3b
ollama list
```

## Commands

```powershell
python hermes_model_router.py status
python hermes_model_router.py providers
python hermes_model_router.py models
python hermes_model_router.py route "Fix a Python syntax error"
python hermes_model_router.py ask "Explain the safest next step"
python hermes_model_router.py test
python hermes_employee.py router
```

## Task route map

| Route | Intended work | Selection fallback |
|---|---|---|
| `compress` | Condense a task | Smallest local model |
| `classify` | Label or categorize | Smallest local model |
| `general` | General planning or answers | Strongest available model |
| `coding` | Code, bugs, syntax, repositories | Preferred coder, then strongest |
| `reasoning` | Architecture and analysis | Preferred reasoner, then strongest |
| `vision` | Images and screenshots | Vision-capable models only |
| `security` | Defensive security work | Preferred coder/security model, then strongest |

## Health and UI visibility

- `GET /health` includes sanitized provider availability and the latest fallback notice.
- `GET /api/status` includes the same provider health summary for UI surfaces.
- Hermes never logs API keys, bearer tokens, or raw prompt contents in router audit output.

## Troubleshooting

- LM Studio offline: open LM Studio, load a model, start its server, and confirm port `1234`.
- Ollama offline: run `ollama serve`, then `ollama list`.
- No models: load a model in LM Studio or pull `qwen2.5:3b` and `llama3.2:3b` with Ollama.
- Wrong route: make the task explicit, such as “compress,” “classify,” “fix Python,” or “inspect this image.”
- Remote URL refused: restore a loopback URL. Do not enable cloud for normal local operation.
