from __future__ import annotations

import json
from pathlib import Path

from backend.services.model_router import ModelRouter
from backend.services.provider_registry import ProviderRegistry
from llm import client as llm_client


class FakeResponse:
    status = 200

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *_args) -> bool:
        return False


def test_ollama_registry_uses_tags_and_discovers_default_model(monkeypatch, tmp_path: Path) -> None:
    requests = []

    def fake_urlopen(request, timeout=2):
        requests.append((request.full_url, timeout))
        return FakeResponse({"models": [{"name": "llama3.2:3b"}]})

    monkeypatch.setattr("backend.services.provider_registry.urllib.request.urlopen", fake_urlopen)
    registry = ProviderRegistry(hermes_dir=tmp_path / ".hermes")

    assert registry.installed_models() == ["llama3.2:3b"]
    assert registry._probe_provider("ollama", registry.providers()["ollama"]) is True
    assert requests[0][0].endswith("/api/tags")


def test_ollama_request_payload_and_response_parsing(monkeypatch) -> None:
    requests = []

    def fake_urlopen(request, timeout=120):
        requests.append(request)
        return FakeResponse({"message": {"content": "Local Hermes response."}})

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)
    result = llm_client._ollama_native_response(
        {"task": {"goal": "Say hello."}},
        "ollama",
        {"base_url": "http://127.0.0.1:11434"},
        "llama3.2:3b",
        {"temperature": 0.2, "max_tokens": 128},
    )

    payload = json.loads(requests[0].data.decode("utf-8"))
    assert requests[0].full_url == "http://127.0.0.1:11434/api/chat"
    assert payload["model"] == "llama3.2:3b"
    assert payload["stream"] is False
    assert "Authorization" not in dict(requests[0].header_items())
    assert result["result"] == "Local Hermes response."
    assert result["meta"] == {"mode": "local", "provider": "ollama", "model": "llama3.2:3b"}


def test_ollama_is_local_and_manual_selection_stays_local(tmp_path: Path) -> None:
    router = ModelRouter(hermes_dir=tmp_path / ".hermes")
    provider = router.provider_registry.providers()["ollama"]
    assert router.provider_registry.is_cloud_provider(provider) is False

    attempts = router._candidate_attempts(
        router.plan_task("Say hello."),
        {"routing_mode": "manual", "preferred_provider": "ollama", "preferred_model": "llama3.2:3b"},
        {},
        None,
    )
    assert [(item["provider"]["name"], item["model"]) for item in attempts] == [("ollama", "llama3.2:3b")]
