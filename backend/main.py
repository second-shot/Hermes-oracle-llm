from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from backend.routes.llm import chat_completion, list_models
from backend.services.ecosystem_control import EcosystemControlPlane
from oracle_v1.service import OracleService
from runtime_state import resolve_data_root


app = FastAPI(title="Hermes Local API")
DASHBOARD_DIR = Path(__file__).resolve().parent / "dashboard"
app.mount("/ui/assets", StaticFiles(directory=DASHBOARD_DIR), name="ui-assets")


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    system: str = "You are Hermes, a local-first operator assistant. Be direct, useful, and low-cost."


@app.get("/")
def root() -> dict[str, str]:
    return {"name": "Hermes Local API", "status": "online", "control_plane": "/ui"}


@app.get("/health")
@app.get("/v1/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "hermes"}


@app.get("/models")
@app.get("/v1/models")
def models() -> dict:
    return list_models()


@app.get("/ui", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(DASHBOARD_DIR / "index.html")


@app.get("/api/ecosystem")
def ecosystem() -> dict:
    return EcosystemControlPlane().snapshot()


def oracle_service() -> OracleService:
    return OracleService(resolve_data_root())


@app.get("/api/oracle/state")
def oracle_state() -> dict:
    return oracle_service().get_state()


@app.get("/api/oracle/events")
def oracle_events() -> dict:
    return oracle_service().list_events()


@app.post("/api/oracle/intake")
def oracle_intake(payload: dict) -> dict:
    return oracle_service().submit_intake(payload)


@app.get("/api/confirmations")
def confirmations() -> dict:
    return oracle_service().list_confirmations()


@app.post("/api/confirmations/{confirmation_id}/approve")
def approve_confirmation(confirmation_id: str, payload: dict | None = None) -> dict:
    return oracle_service().approve_confirmation(confirmation_id, payload)


@app.post("/api/confirmations/{confirmation_id}/reject")
def reject_confirmation(confirmation_id: str, payload: dict | None = None) -> dict:
    return oracle_service().reject_confirmation(confirmation_id, payload)


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
