from __future__ import annotations

from pathlib import Path
import json
import threading
import time
import urllib.request

import pytest

from backend.services.credit_guard import CLOUD_UNLOCK_PHRASE, CreditGuard
from backend.services.local_cache import LocalCache
from backend.services.model_router import ModelRouter
from backend.services.provider_registry import ProviderRegistry, sanitize_provider
from backend.services.repo_indexer import RepoIndexer
from backend.routes.llm import run_server
from llm import client as llm_client


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config/hermes.model.rotation.yaml"


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


def runtime_cloud_config() -> dict:
    return {
        "cloud_enabled": True,
        "llm": {"provider": "openai", "model": "gpt-4o-mini"},
    }


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


@pytest.mark.parametrize(
    ("primary_failure", "openrouter_failure"),
    [
        (
            {
                "error": "provider-failure",
                "failure_reason": "http_402_payment_required",
                "retryable": True,
                "cooldown_seconds": 900,
            },
            {
                "error": "provider-failure",
                "failure_reason": "http_429_rate_limit",
                "retryable": True,
                "cooldown_seconds": 300,
            },
        ),
        (
            {
                "error": "provider-failure",
                "failure_reason": "insufficient_credits",
                "retryable": True,
                "cooldown_seconds": 900,
            },
            TimeoutError("openrouter timed out"),
        ),
        (
            {
                "error": "provider-failure",
                "failure_reason": "exhausted_quota",
                "retryable": True,
                "cooldown_seconds": 900,
            },
            {
                "error": "provider-failure",
                "failure_reason": "model_unavailable",
                "retryable": True,
                "cooldown_seconds": 600,
            },
        ),
        (
            OSError("primary provider unavailable"),
            {
                "error": "provider-failure",
                "failure_reason": "connection_failure",
                "retryable": True,
                "cooldown_seconds": 120,
            },
        ),
    ],
)
def test_router_falls_back_in_deterministic_order_without_losing_context(
    tmp_path: Path,
    primary_failure,
    openrouter_failure,
) -> None:
    router = make_router(tmp_path)
    router.config["fallback"] = {"openrouter_free_models": ["openrouter/free-model"]}

    memory_snapshots: list[object] = []
    repo_indexes: list[object] = []
    calls: list[tuple[str, str]] = []

    def infer(attempt: dict) -> dict:
        provider_name = attempt["provider"]["name"]
        calls.append((provider_name, attempt["model"]))
        memory_snapshots.append(attempt.get("memory"))
        repo_indexes.append(attempt.get("repo_index"))
        if provider_name == "openai":
            if isinstance(primary_failure, Exception):
                raise primary_failure
            return primary_failure
        if provider_name == "openrouter_free":
            if isinstance(openrouter_failure, Exception):
                raise openrouter_failure
            return openrouter_failure
        return {
            "result": "local ollama recovered the task",
            "meta": {"provider": provider_name, "model": attempt["model"]},
        }

    result = router.run_task(
        "debug this repo bug and inspect the traceback carefully",
        infer,
        runtime_config=runtime_cloud_config(),
        mentioned_files=["src/main.py"],
    )

    assert calls == [
        ("openai", "gpt-4o-mini"),
        ("ollama", "llama3.2:3b"),
    ]
    assert result["result"] == "local ollama recovered the task"
    assert result["meta"]["provider"] == "ollama"
    assert result["fallback_notice"] == "Cloud credits exhausted. Switched to local offline model."
    assert all(snapshot == {"recent": ["cached project context"]} for snapshot in memory_snapshots)
    assert repo_indexes[0] == repo_indexes[1]

    audit_entries = json.loads((tmp_path / ".hermes" / "logs" / "model_router_audit.json").read_text(encoding="utf-8"))
    assert audit_entries[-1]["final_provider"] == "ollama"
    assert audit_entries[-1]["attempts"][0]["failure_reason"] in {
        "http_402_payment_required",
        "insufficient_credits",
        "exhausted_quota",
        "provider_unavailable",
    }
    assert "debug this repo bug" not in json.dumps(audit_entries[-1])
    assert "test-token" not in json.dumps(audit_entries[-1])


def test_router_places_temporarily_failing_providers_on_cooldown(tmp_path: Path) -> None:
    router = make_router(tmp_path)
    router.config["fallback"] = {"openrouter_free_models": ["openrouter/free-model"]}
    calls: list[tuple[str, str]] = []

    def infer(attempt: dict) -> dict:
        provider_name = attempt["provider"]["name"]
        calls.append((provider_name, attempt["model"]))
        if provider_name == "openai":
            return {
                "error": "provider-failure",
                "failure_reason": "http_429_rate_limit",
                "retryable": True,
                "cooldown_seconds": 300,
            }
        if provider_name == "openrouter_free":
            return {
                "error": "provider-failure",
                "failure_reason": "provider_unavailable",
                "retryable": True,
                "cooldown_seconds": 60,
            }
        return {"result": "local fallback", "meta": {"provider": provider_name, "model": attempt["model"]}}

    first = router.run_task("Say Hermes is ready.", infer, runtime_config=runtime_cloud_config())
    second = router.run_task("Say Hermes is ready again.", infer, runtime_config=runtime_cloud_config())

    assert first["meta"]["provider"] == "ollama"
    assert second["meta"]["provider"] == "ollama"
    assert calls == [
        ("openai", "gpt-4o-mini"),
        ("openrouter_free", "openrouter/free-model"),
        ("ollama", "llama3.2:3b"),
        ("ollama", "llama3.2:3b"),
    ]


def test_router_does_not_retry_auth_failures_indefinitely(tmp_path: Path) -> None:
    router = make_router(tmp_path)
    router.config["fallback"] = {"openrouter_free_models": ["openrouter/free-model"]}
    calls: list[tuple[str, str]] = []

    def infer(attempt: dict) -> dict:
        provider_name = attempt["provider"]["name"]
        calls.append((provider_name, attempt["model"]))
        if provider_name == "openai":
            return {
                "error": "provider-failure",
                "failure_reason": "authentication_failed",
                "retryable": False,
                "cooldown_seconds": 300,
            }
        if provider_name == "openrouter_free":
            return {
                "error": "provider-failure",
                "failure_reason": "authentication_failed",
                "retryable": False,
                "cooldown_seconds": 300,
            }
        return {"result": "ollama answered", "meta": {"provider": provider_name, "model": attempt["model"]}}

    result = router.run_task("Give a short answer.", infer, runtime_config=runtime_cloud_config())

    assert result["meta"]["provider"] == "ollama"
    assert calls == [
        ("openai", "gpt-4o-mini"),
        ("openrouter_free", "openrouter/free-model"),
        ("ollama", "llama3.2:3b"),
    ]


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


def test_sanitized_provider_keeps_token_selector_without_sending_redaction_marker(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("LM_STUDIO_API_TOKEN", raising=False)
    monkeypatch.delenv("LM_API_TOKEN", raising=False)
    provider = make_registry(tmp_path).providers()["lmstudio_windows"]
    provider_config = sanitize_provider("lmstudio_windows", provider)

    assert provider_config["env_key"] == "LM_STUDIO_API_TOKEN"
    assert provider_config["api_key"] == "<redacted>"
    assert llm_client._provider_api_token(provider_config) is None

    monkeypatch.setenv("LM_STUDIO_API_TOKEN", "test-token")

    assert llm_client._provider_api_token(provider_config) == "test-token"


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


def test_local_client_accepts_lm_api_token_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    requests = []

    def fake_urlopen(request, timeout=20):
        requests.append(request)
        if request.full_url.endswith("/models"):
            return _FakeHttpResponse({"data": [{"id": "actual-local-model"}]})
        return _FakeHttpResponse({"choices": [{"message": {"content": "Hermes is alive."}}]})

    monkeypatch.setenv("LM_API_TOKEN", "alias-token")
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
    assert dict(requests[0].header_items())["Authorization"] == "Bearer alias-token"


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


def test_hermes_api_serves_models_and_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(REPO_ROOT)
    thread = threading.Thread(target=run_server, kwargs={"host": "127.0.0.1", "port": 8011}, daemon=True)
    thread.start()
    time.sleep(1.0)

    models = json.loads(urllib.request.urlopen("http://127.0.0.1:8011/v1/models", timeout=10).read().decode("utf-8"))
    assert models["object"] == "list"
    assert models["data"]

    payload = {
        "model": models["data"][0]["id"],
        "messages": [{"role": "user", "content": "Say Hermes is ready."}],
    }
    request = urllib.request.Request(
        "http://127.0.0.1:8011/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    chat = json.loads(urllib.request.urlopen(request, timeout=30).read().decode("utf-8"))
    assert chat["object"] == "chat.completion"
    assert chat["choices"][0]["message"]["role"] == "assistant"
