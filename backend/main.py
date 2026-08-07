from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from backend.routes.llm import chat_completion, list_models, provider_health
from resale_agents.service import ConflictError, ResaleAgentService


app = FastAPI(title="Hermes Local API")
resale_service = ResaleAgentService.from_repo_root()


def _sanitize_provider_health(payload: dict) -> dict:
    providers = []
    for provider in payload.get("providers", []):
        if not isinstance(provider, dict):
            continue
        providers.append({key: value for key, value in provider.items() if key not in {"api_key", "token", "authorization"}})
    return {
        "router_status": payload.get("router_status", "unknown"),
        "active_mode": payload.get("active_mode", "hybrid"),
        "selected_provider": payload.get("selected_provider"),
        "selected_model": payload.get("selected_model"),
        "execution_scope": payload.get("execution_scope", "unknown"),
        "available_providers": payload.get("available_providers", []),
        "local_ollama_available": bool(payload.get("local_ollama_available", False)),
        "fallback_active": bool(payload.get("fallback_active", False)),
        "providers": providers,
        "last_fallback_notice": payload.get("last_fallback_notice"),
        "fallback_reason": payload.get("fallback_reason"),
    }


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    system: str = "You are Hermes, a local-first operator assistant. Be direct, useful, and low-cost."


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "Hermes Local API", "status": "online"}


@app.get("/health")
@app.get("/v1/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "hermes",
        "resale_agents": resale_service.health(),
        "provider_health": _sanitize_provider_health(provider_health()),
    }


@app.get("/api/status")
def api_status() -> dict:
    return {"status": "ok", "service": "hermes", "provider_health": _sanitize_provider_health(provider_health())}


@app.post("/v1/resale/items", status_code=201)
def capture_resale_item(payload: dict) -> dict:
    return resale_service.capture_item(payload)


@app.get("/v1/resale/items/{item_id}")
def get_resale_item(item_id: str) -> dict:
    return resale_service.get_item(item_id)


@app.post("/v1/resale/items/{item_id}/run")
def run_resale_workflow(item_id: str) -> dict:
    results = resale_service.run_until_approval(item_id)
    return {"item": resale_service.get_item(item_id), "results": [result.to_dict() for result in results]}


@app.get("/v1/resale/tasks")
def resale_tasks() -> dict:
    return {"items": resale_service.list_tasks()}


@app.get("/v1/resale/approvals")
def resale_approvals() -> dict:
    return {"items": resale_service.list_approvals()}


@app.get("/models")
@app.get("/v1/models")
def models() -> dict:
    return list_models()


@app.post("/chat")
def chat(request: ChatRequest) -> dict:
    payload = {
        "model": request.model or "hermes-local",
        "messages": [
            {"role": "system", "content": request.system},
            {"role": "user", "content": request.message},
        ],
    }
    return chat_completion(payload)


@app.post("/v1/chat/completions")
def chat_completions(payload: dict) -> dict:
    return chat_completion(payload)
