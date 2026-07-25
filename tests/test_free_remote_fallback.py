from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.services.credit_guard import CreditGuard
from backend.services.local_cache import LocalCache
from backend.services.model_router import ModelRouter
from backend.services.provider_registry import ProviderRegistry
from backend.services.repo_indexer import RepoIndexer
from llm.free_remote import call_free_remote


CONFIG_PATH = Path("config/hermes.model.rotation.yaml")


def make_router(tmp_path: Path) -> ModelRouter:
    hermes_dir = tmp_path / ".hermes"
    return ModelRouter(
        config_path=CONFIG_PATH,
        hermes_dir=hermes_dir,
        provider_registry=ProviderRegistry(config_path=CONFIG_PATH, hermes_dir=hermes_dir),
        credit_guard=CreditGuard(config_path=CONFIG_PATH, hermes_dir=hermes_dir),
        cache=LocalCache(config_path=CONFIG_PATH, hermes_dir=hermes_dir),
        repo_indexer=RepoIndexer(project_root=tmp_path, config_path=CONFIG_PATH, hermes_dir=hermes_dir),
        memory_reader=lambda _plan: {},
    )


def verified_provider() -> dict:
    return {
        "enabled": True,
        "type": "openai_compatible",
        "base_url": "https://free.example.test/v1",
        "cost": "free",
        "explicit_opt_in": True,
        "verified_zero_cost": True,
        "free_model_only": True,
    }


def test_credit_guard_allows_only_explicit_verified_free_remote(tmp_path: Path) -> None:
    guard = CreditGuard(config_path=CONFIG_PATH, hermes_dir=tmp_path / ".hermes")

    allowed = guard.can_use_provider("free_remote", verified_provider())
    blocked = guard.can_use_provider(
        "free_remote",
        {**verified_provider(), "verified_zero_cost": False},
    )

    assert allowed.allowed is True
    assert blocked.allowed is False


def test_paid_provider_remains_blocked_even_with_free_markers(tmp_path: Path) -> None:
    guard = CreditGuard(config_path=CONFIG_PATH, hermes_dir=tmp_path / ".hermes")
    provider = {**verified_provider(), "cost": "paid"}

    decision = guard.can_use_provider("free_remote", provider)

    assert decision.allowed is False
    assert "paid" in decision.reason.lower()


def test_router_tries_local_before_verified_free_remote(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = make_router(tmp_path)
    local = SimpleNamespace(
        name="lmstudio_windows",
        provider={"name": "lmstudio_windows", "base_url": "http://localhost:1234/v1"},
        available=True,
        is_cloud=False,
        priority=1,
        routing_score=1.0,
    )
    monkeypatch.setattr(router.provider_registry, "available_providers", lambda *_args, **_kwargs: [local])
    monkeypatch.setenv("HERMES_ENABLE_FREE_REMOTE", "1")
    monkeypatch.setenv("HERMES_FREE_REMOTE_VERIFIED_ZERO_COST", "1")
    monkeypatch.setenv("HERMES_FREE_REMOTE_BASE_URL", "https://free.example.test/v1")
    monkeypatch.setenv("HERMES_FREE_REMOTE_MODEL", "provider/free-model")

    attempts: list[str] = []

    def infer(attempt: dict):
        provider_name = attempt["provider"]["name"]
        attempts.append(provider_name)
        if attempt["provider"].get("is_cloud"):
            return {"result": "free fallback worked"}
        return None

    result = router.run_task("help with this plan", infer)

    assert attempts == ["lmstudio_windows", "free_remote"]
    assert result["result"] == "free fallback worked"
    assert result["route_class"] == "free-remote"


def test_router_never_attempts_remote_without_explicit_opt_in(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = make_router(tmp_path)
    monkeypatch.setattr(router.provider_registry, "available_providers", lambda *_args, **_kwargs: [])
    monkeypatch.delenv("HERMES_ENABLE_FREE_REMOTE", raising=False)
    attempts: list[dict] = []

    result = router.run_task("help with this plan", lambda attempt: attempts.append(attempt))

    assert attempts == []
    assert result["error"] == "local-runtime-missing"
    assert result["fallback_status"] == "disabled"


def test_free_remote_client_rejects_unverified_provider() -> None:
    result = call_free_remote(
        {"task": {"goal": "test"}},
        "free_remote",
        {"base_url": "https://free.example.test/v1", "cost": "free"},
        "provider/free-model",
        {},
    )

    assert result is None


class _FakeResponse:
    status = 200

    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_free_remote_client_uses_exact_model_and_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests = []

    def fake_urlopen(request, timeout=120):
        requests.append(request)
        return _FakeResponse({"choices": [{"message": {"content": "free response"}}]})

    monkeypatch.setenv("TEST_FREE_TOKEN", "secret-test-token")
    monkeypatch.setattr("llm.free_remote.urllib.request.urlopen", fake_urlopen)
    provider = {
        **verified_provider(),
        "env_key": "TEST_FREE_TOKEN",
        "request_timeout_seconds": 30,
    }

    result = call_free_remote(
        {"task": {"goal": "test"}},
        "free_remote",
        provider,
        "provider/free-model",
        {"max_tokens": 100},
    )

    assert result is not None
    assert result["result"] == "free response"
    assert result["meta"]["verified_zero_cost"] is True
    assert dict(requests[0].header_items())["Authorization"] == "Bearer secret-test-token"
    payload = json.loads(requests[0].data.decode("utf-8"))
    assert payload["model"] == "provider/free-model"
