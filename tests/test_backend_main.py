from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app


def test_fastapi_adapter_serves_health() -> None:
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["resale_agents"] == {"status": "unavailable"}


def test_missing_optional_resale_agents_do_not_block_backend_startup() -> None:
    client = TestClient(app)

    response = client.get("/v1/resale/tasks")

    assert response.status_code == 503
    assert response.json()["detail"] == "Resale agents are not installed in this repository checkout."


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
