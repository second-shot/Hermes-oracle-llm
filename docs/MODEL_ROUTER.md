# Hermes Offline Model Router

Hermes routes model work locally in this order:

1. Refraction normalizes and bounds task text.
2. MIA classifies risk and enforces existing approval gates.
3. The router classifies safe/approved text as `compress`, `classify`, `general`, `coding`, `reasoning`, `vision`, or `security`.
4. It checks LM Studio first and Ollama second.
5. It chooses an exact preferred model or a route-appropriate size fallback.
6. It logs the route, provider, model, and status to `data/router/model_router_log.json`.
7. If neither provider is online, Hermes uses deterministic no-model planning.

Compression happens before model selection so repeated whitespace and oversized raw task text do not waste local context. Risk checks still use the original task, and compression never grants permission or bypasses approval.

## Local endpoints

- LM Studio primary: `http://127.0.0.1:1234/v1`
- LM Studio fallback: `http://localhost:1234/v1`
- Ollama native: `http://localhost:11434/api`
- Ollama OpenAI-compatible: `http://localhost:11434/v1`

Remote URLs are refused unless explicitly allowlisted. `api.openai.com` is refused while `cloud_enabled` is false. The checked-in router configuration is local-only, has no cloud fallback, and uses no paid API credits.

Provider HTTP requests ignore ambient proxy settings and refuse redirects, keeping prompts and the optional LM Studio token on the validated endpoint.

## Start LM Studio

Open LM Studio, load a model, open its Developer/Local Server view, select port `1234`, and start the server. Verify with:

```powershell
python scripts/check_lm_studio.py
```

## Start Ollama

Install and start Ollama locally, then pull or run a model. For example:

```powershell
ollama serve
ollama list
```

The router discovers Ollama models through `GET http://localhost:11434/api/tags`.

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

## Fallback rules

- Online LM Studio is considered first.
- If LM Studio is offline, online Ollama is considered.
- If both are offline, the route status is `NO_LOCAL_MODEL_ONLINE` and MIA returns deterministic planning text.
- If a vision request has no vision-capable model, the router returns `NO_MATCHING_LOCAL_MODEL` instead of sending image work to a text-only model.
- Routing does not authorize execution. MIA's risk and approval gates remain authoritative.

## Troubleshooting

- LM Studio offline: open LM Studio, load a model, start its server, and confirm port `1234`.
- Ollama offline: run `ollama serve`, then `ollama list`.
- No models: load a model in LM Studio or pull one with Ollama.
- Wrong route: make the task explicit, such as “compress,” “classify,” “fix Python,” or “inspect this image.”
- Remote URL refused: restore a loopback URL. Do not enable cloud for normal local operation.
