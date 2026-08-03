# Offline Model Router Design

Hermes routes local model work through a focused standard-library adapter. The adapter loads `config/model_router.json`, probes LM Studio before Ollama, normalizes each provider's model-list response, classifies task text into one of seven routes, and selects an exact preferred model or a size-based fallback appropriate to the route.

All provider URLs pass the shared loopback policy in `hermes_provider.py`. A remote URL must appear in `allowed_remote_urls`; `api.openai.com` additionally requires `cloud_enabled: true`. The checked-in configuration enables neither condition, so normal operation cannot spend cloud credits.

Routing is separate from authorization. `hermes_employee.py` keeps risk classification and approval gates before calling the router. Low-risk and already-approved work may request local planning text; an unavailable provider yields `NO_LOCAL_MODEL_ONLINE` and deterministic planning text without changing task permission.

Route decisions append sanitized provider/model metadata to `data/router/model_router_log.json`. Tests inject local provider responses rather than requiring a running model server, covering LM Studio priority, Ollama fallback, size-aware selection, vision restrictions, remote URL rejection, deterministic fallback, and MIA CLI integration.
