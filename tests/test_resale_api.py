from __future__ import annotations

from fastapi.testclient import TestClient

from backend.main import app
from backend.routes import resale as resale_routes


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("HERMES_DATA_DIR", str(tmp_path / "hermes-data"))
    resale_routes.get_store.cache_clear()
    return TestClient(app)


def test_resale_api_capture_queue_and_transition(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    created = client.post(
        "/api/resale/items",
        json={
            "title": "Rare soul record",
            "category": "vinyl",
            "priority": "HIGH",
            "target_price": 120,
            "research_confidence": 0.8,
            "expected_effort_minutes": 10,
        },
    )

    assert created.status_code == 201
    body = created.json()
    assert body["external_action"] is False
    item_id = body["item"]["id"]

    queue = client.get("/api/resale/queue").json()
    assert queue["count"] == 1
    assert queue["external_action"] is False
    assert queue["queue"][0]["item_id"] == item_id

    transitioned = client.post(
        f"/api/resale/items/{item_id}/status",
        json={"status": "READY", "note": "Exact pressing confirmed"},
    )
    assert transitioned.status_code == 200
    assert transitioned.json()["item"]["status"] == "READY"
    assert transitioned.json()["external_action"] is False


def test_resale_api_import_preview_does_not_commit(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)
    payload = """[
      {
        "title": "Preview magazine",
        "category": "magazine",
        "status": "CAPTURED",
        "priority": "MEDIUM",
        "target_price": 20
      }
    ]"""

    response = client.post("/api/resale/import/json", json={"payload": payload, "preview": True})

    assert response.status_code == 200
    assert response.json()["preview"] is True
    assert response.json()["count"] == 1
    assert client.get("/api/resale/items").json()["count"] == 0


def test_resale_api_rejects_invalid_item_and_missing_transition(tmp_path, monkeypatch) -> None:
    client = make_client(tmp_path, monkeypatch)

    invalid = client.post("/api/resale/items", json={"title": ""})
    missing = client.post("/api/resale/items/not-found/status", json={"status": "SOLD"})

    assert invalid.status_code == 422
    assert missing.status_code == 404
