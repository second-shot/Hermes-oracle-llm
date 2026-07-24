from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.main import app


def test_fastapi_adapter_serves_health() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_fastapi_adapter_serves_chat(monkeypatch) -> None:
    from backend import main as backend_main

    client = TestClient(app)
    monkeypatch.setattr(
        backend_main,
        "chat_completion",
        lambda payload: {
            "object": "chat.completion",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": f"Echo: {payload['messages'][-1]['content']}"},
                    "finish_reason": "stop",
                }
            ],
        },
    )

    response = client.post("/chat", json={"message": "Say Hermes API is working."})

    assert response.status_code == 200
    assert response.json()["choices"][0]["message"]["content"] == "Echo: Say Hermes API is working."


def test_control_plane_serves_dashboard_and_ecosystem(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HERMES_DATA_DIR", str(tmp_path / "runtime"))
    client = TestClient(app)

    dashboard = client.get("/ui")
    styles = client.get("/ui/assets/styles.css")
    ecosystem = client.get("/api/ecosystem")
    oracle = client.get("/api/oracle/state")
    intake = client.post(
        "/api/oracle/intake",
        json={
            "mode": "architect",
            "text": "Summarize the local Hermes module health.",
            "objective": "Return one safe next checkpoint.",
        },
    )

    assert dashboard.status_code == 200
    assert "HERMES" in dashboard.text
    assert styles.status_code == 200
    assert "--copper" in styles.text
    assert ecosystem.status_code == 200
    assert ecosystem.json()["cost"]["default_cost_usd"] == 0
    assert ecosystem.json()["cost"]["cloud_auto_fallback"] is False
    assert oracle.status_code == 200
    assert oracle.json()["status"] == "ok"
    assert intake.status_code == 200
    assert intake.json()["data"]["requiresConfirmation"] is False
