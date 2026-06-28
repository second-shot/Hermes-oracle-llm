from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from backend.routes.llm import chat_completion, list_models


app = FastAPI(title="Hermes Local API")


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    system: str = "You are Hermes, a local-first operator assistant. Be direct, useful, and low-cost."


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "Hermes Local API", "status": "online"}


@app.get("/health")
@app.get("/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "hermes"}


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
