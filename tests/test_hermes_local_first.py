from __future__ import annotations

from pathlib import Path
import json

import pytest

from backend.services.credit_guard import CLOUD_UNLOCK_PHRASE, CreditGuard
from backend.services.local_cache import LocalCache
from backend.services.model_router import ModelRouter
from backend.services.provider_registry import ProviderRegistry
from backend.services.repo_indexer import RepoIndexer
from llm import client as llm_client


CONFIG_PATH = Path("config/hermes.model.rotation.yaml")


def make_guard(tmp_path: Path) -> CreditGuard:
    return CreditGuard(config_path=CONFIG_PATH, hermes_dir=tmp_path / ".hermes")


def make_registry(tmp_path: Path) -> ProviderRegistry:
    return ProviderRegistry(config_path=CONFIG_PATH, hermes_dir=tmp_path / ".hermes")


def make_router(tmp_path: Path) -> ModelRouter:
    hermes_dir = tmp_path / ".hermes"
    return ModelRouter(
        config_path=CONFIG_PATH,
        hermes_dir=hermes_dir,
        provider_registry=ProviderRegistry(config_path=CONFIG_PATH, hermes_dir=hermes_dir),
        credit_guard=CreditGuard(config_path=CONFIG_PATH, hermes_dir=hermes_dir),
        cache=LocalCache(config_path=CONFIG_PATH, hermes_dir=hermes_dir),
        repo_indexer=RepoIndexer(project_root=tmp_path, config_path=CONFIG_PATH, hermes_dir=hermes_dir),
        memory_reader=lambda _: {"recent": ["cached project context"]},
    )


def test_paid_cloud_provider_is_blocked_by_default(tmp_path: Path) -> None:
    guard = make_guard(tmp_path)

    allowed = guard.can_use_provider(
        "openrouter_locked",
        {"cost": "paid", "type": "openai_compatible", "base_url": "https://openrouter.ai/api/v1"},
    )

    assert allowed.allowed is False
    assert "paid" in allowed.reason.lower()


def test_unlock_phrase_enables_cloud_for_one_task_only(tmp_path: Path) -> None:
    guard = make_guard(tmp_path)

    assert guard.unlock_for_task(CLOUD_UNLOCK_PHRASE) is True
    first_check = guard.can_use_provider(
        "openrouter_locked",
        {"cost": "free", "type": "openai_compatible", "base_url": "https://openrouter.ai/api/v1"},
    )
    guard.complete_task()
    second_check = guard.can_use_provider(
        "openrouter_locked",
        {"cost": "free", "type": "openai_compatible", "base_url": "https://openrouter.ai/api/v1"},
    )

    assert first_check.allowed is True
    assert second_check.allowed is False


def test_unlock_resets_after_one_task(tmp_path: Path) -> None:
    guard = make_guard(tmp_path)

    guard.unlock_for_task(CLOUD_UNLOCK_PHRASE)
    guard.complete_task()

    allowed = guard.can_use_provider(
        "openrouter_locked",
        {"cost": "free", "type": "openai_compatible", "base_url": "https://openrouter.ai/api/v1"},
    )

    assert allowed.allowed is False


def test_router_chooses_coding_model_for_repo_debug(tmp_path: Path) -> None:
    router = make_router(tmp_path)

    plan = router.plan_task("debug this repo failure in the tests and inspect the code path")

    assert plan["task_route"] == "repo_debug"
    assert plan["model_key"] == "coding"


def test_router_chooses_coding_model_for_code_patch(tmp_path: Path) -> None:
    router = make_router(tmp_path)

    plan = router.plan_task("patch this function and update the implementation safely")

    assert plan["task_route"] == "code_patch"
    assert plan["model_key"] == "coding"


def test_router_chooses_vision_model_for_screenshot_image_tasks(tmp_path: Path) -> None:
    router = make_router(tmp_path)

    plan = router.plan_task("please inspect this screenshot and image artifact")

    assert plan["task_route"] == "screenshot_or_image"
    assert plan["model_key"] == "vision"


def test_cache_is_checked_before_model_inference(tmp_path: Path) -> None:
    router = make_router(tmp_path)
    plan = router.plan_task("summarise this project memory for me")
    cache_key = router.build_cache_key("summarise this project memory for me", plan)
    router.cache.set_model_output(cache_key, {"result": "cache hit"})
    calls: list[str] = []

    def infer(_attempt: dict) -> dict:
        calls.append("called")
        return {"result": "live"}

    result = router.run_task("summarise this project memory for me", infer)

    assert result["source"] == "cache"
    assert result["result"] == "cache hit"
    assert calls == []


def test_repo_indexer_does_not_scan_ignored_folders(tmp_path: Path) -> None:
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("console.log('ignore')", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "main.py").write_text("print('keep')\n", encoding="utf-8")

    indexer = RepoIndexer(project_root=tmp_path, config_path=CONFIG_PATH, hermes_dir=tmp_path / ".hermes")
    index = indexer.build_index(startup=False, mentioned_files=["src/main.py"])

    assert "src/main.py" in index["files"]
    assert "node_modules/ignored.js" not in index["files"]


def test_missing_lm_studio_server_does_not_crash_hermes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    router = make_router(tmp_path)
    monkeypatch.setattr(router.provider_registry, "_probe_provider", lambda *_args, **_kwargs: False)

    result = router.run_task("help me plan a task", lambda _attempt: {"result": "should not run"})

    assert result["error"] == "local-runtime-missing"


def test_openrouter_is_not_called_when_cloud_auto_fallback_is_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    router = make_router(tmp_path)
    calls: list[str] = []

    def fake_probe(name: str, _provider: dict) -> bool:
        calls.append(name)
        return False

    monkeypatch.setattr(router.provider_registry, "_probe_provider", fake_probe)

    result = router.run_task("debug this repo bug", lambda _attempt: {"result": "should not run"})

    assert result["error"] == "local-runtime-missing"
    assert "openrouter_locked" not in calls


class _FakeHttpResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.status = 200

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self) -> "_FakeHttpResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_local_client_omits_placeholder_auth_and_uses_discovered_model(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = []

    def fake_urlopen(request, timeout=20):
        requests.append(request)
        if request.full_url.endswith("/models"):
            return _FakeHttpResponse({"data": [{"id": "actual-local-model"}]})
        return _FakeHttpResponse({"choices": [{"message": {"content": "Hermes is alive."}}]})

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)

    result = llm_client._openai_compatible_local_response(
        {"task": {"goal": "Say Hermes local runtime is alive in one sentence."}},
        "lmstudio_windows",
        {"base_url": "http://localhost:1234/v1", "api_key": "lm-studio"},
        "qwen3-4b-instruct-q4",
        {"temperature": 0.2},
    )

    assert result is not None
    assert result["result"] == "Hermes is alive."
    assert "Authorization" not in dict(requests[0].header_items())
    chat_payload = json.loads(requests[1].data.decode("utf-8"))
    assert chat_payload["model"] == "actual-local-model"


def test_local_client_uses_env_token_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = []

    def fake_urlopen(request, timeout=20):
        requests.append(request)
        if request.full_url.endswith("/models"):
            return _FakeHttpResponse({"data": [{"id": "actual-local-model"}]})
        return _FakeHttpResponse({"choices": [{"message": {"content": "Hermes is alive."}}]})

    monkeypatch.setenv("LM_STUDIO_API_TOKEN", "test-token")
    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)

    result = llm_client._openai_compatible_local_response(
        {"task": {"goal": "Say Hermes local runtime is alive in one sentence."}},
        "lmstudio_windows",
        {"base_url": "http://localhost:1234/v1", "env_key": "LM_STUDIO_API_TOKEN", "api_key": ""},
        "qwen3-4b-instruct-q4",
        {"temperature": 0.2},
    )

    assert result is not None
    assert result["result"] == "Hermes is alive."
    assert dict(requests[0].header_items())["Authorization"] == "Bearer test-token"


def test_local_client_uses_extended_timeout_for_local_inference(monkeypatch: pytest.MonkeyPatch) -> None:
    timeouts = []

    def fake_urlopen(request, timeout=20):
        timeouts.append(timeout)
        if request.full_url.endswith("/models"):
            return _FakeHttpResponse({"data": [{"id": "actual-local-model"}]})
        return _FakeHttpResponse({"choices": [{"message": {"content": "Hermes is alive."}}]})

    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)

    result = llm_client._openai_compatible_local_response(
        {"task": {"goal": "Say Hermes local runtime is alive in one sentence."}},
        "lmstudio_windows",
        {"base_url": "http://localhost:1234/v1"},
        "qwen3-4b-instruct-q4",
        {"temperature": 0.2},
    )

    assert result is not None
    assert timeouts == [20, 120]
