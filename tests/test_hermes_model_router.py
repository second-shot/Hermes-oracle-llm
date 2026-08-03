import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import ProxyHandler

import pytest


ROOT = Path(__file__).resolve().parents[1]


def provider_states(lm_online=True, ollama_online=True):
    return {
        "lm_studio": {
            "online": lm_online,
            "base_url": "http://127.0.0.1:1234/v1",
            "models": ["qwen2.5-coder:7b", "qwen2.5:0.5b", "qwen3:8b", "qwen2.5vl:7b"] if lm_online else [],
        },
        "ollama": {
            "online": ollama_online,
            "base_url": "http://localhost:11434/api",
            "models": ["llama3.2:1b", "llama3.2:3b"] if ollama_online else [],
        },
    }


class FakeResponse:
    def __init__(self, body):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class SequencedOpener:
    def __init__(self, outcomes):
        self.outcomes = iter(outcomes)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return FakeResponse(outcome)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Compress this task into one next move", "compress"),
        ("Classify the risk of this task", "classify"),
        ("Fix a Python syntax error", "coding"),
        ("Reason carefully about the architecture", "reasoning"),
        ("Inspect this screenshot", "vision"),
        ("Create a defensive threat model", "security"),
        ("Tell me what to do next", "general"),
    ],
)
def test_classify_task_routes(text, expected):
    from hermes_model_router import classify_task

    assert classify_task(text) == expected


def test_lm_studio_is_selected_before_ollama(tmp_path, monkeypatch):
    import hermes_model_router as router

    monkeypatch.setattr(router, "LOG_PATH", tmp_path / "router.json")
    decision = router.route_task("Fix a Python syntax error", states=provider_states())
    assert decision["provider"] == "lm_studio"
    assert decision["model"] == "qwen2.5-coder:7b"


def test_ollama_is_selected_when_lm_studio_is_offline(tmp_path, monkeypatch):
    import hermes_model_router as router

    monkeypatch.setattr(router, "LOG_PATH", tmp_path / "router.json")
    decision = router.route_task("Give a general answer", states=provider_states(lm_online=False))
    assert decision["provider"] == "ollama"
    assert decision["model"] == "llama3.2:3b"


def test_tiny_route_uses_smallest_model(tmp_path, monkeypatch):
    import hermes_model_router as router

    monkeypatch.setattr(router, "LOG_PATH", tmp_path / "router.json")
    decision = router.route_task("Compress this long task", states=provider_states())
    assert decision["model"] == "qwen2.5:0.5b"


def test_chat_route_excludes_embedding_models(tmp_path, monkeypatch):
    import hermes_model_router as router

    monkeypatch.setattr(router, "LOG_PATH", tmp_path / "router.json")
    states = {
        "lm_studio": {
            "online": True,
            "base_url": "http://127.0.0.1:1234/v1",
            "models": ["qwen2.5-vl-3b-instruct", "text-embedding-nomic-embed-text-v1.5"],
        },
        "ollama": {"online": False, "base_url": None, "models": []},
    }
    decision = router.route_task("Reply with a short answer", states=states)
    assert decision["model"] == "qwen2.5-vl-3b-instruct"


def test_vision_route_only_uses_vision_model(tmp_path, monkeypatch):
    import hermes_model_router as router

    monkeypatch.setattr(router, "LOG_PATH", tmp_path / "router.json")
    decision = router.route_task("Inspect this image", states=provider_states())
    assert decision["model"] == "qwen2.5vl:7b"
    no_vision = provider_states()
    no_vision["lm_studio"]["models"] = ["qwen3:8b"]
    decision = router.route_task("Inspect this image", states=no_vision)
    assert decision["model"] is None


def test_offline_route_returns_deterministic_fallback(tmp_path, monkeypatch):
    import hermes_model_router as router

    monkeypatch.setattr(router, "LOG_PATH", tmp_path / "router.json")
    decision = router.route_task("Explain the task", states=provider_states(False, False))
    assert decision["status"] == "NO_LOCAL_MODEL_ONLINE"
    assert decision["provider"] == "deterministic"
    assert router.ask_task("Explain the task", decision=decision)["response"] == "NO_LOCAL_MODEL_ONLINE"


def test_chat_failure_falls_through_to_healthy_ollama(tmp_path, monkeypatch):
    import hermes_model_router as router

    monkeypatch.setattr(router, "LOG_PATH", tmp_path / "router.json")
    opener = SequencedOpener([URLError("LM chat failed"), {"message": {"content": "Ollama answered"}}])
    monkeypatch.setattr(router, "LOCAL_OPENER", opener)
    decision = router.route_task("Give a general answer", states=provider_states())
    result = router.ask_task("Give a general answer", decision=decision)
    assert result["provider"] == "ollama"
    assert result["response"] == "Ollama answered"
    assert result["status"] == "LOCAL_MODEL_RESPONSE"


def test_failed_chat_outcome_is_logged(tmp_path, monkeypatch):
    import hermes_model_router as router

    log_path = tmp_path / "router.json"
    monkeypatch.setattr(router, "LOG_PATH", log_path)
    monkeypatch.setattr(router, "LOCAL_OPENER", SequencedOpener([URLError("LM failed"), URLError("Ollama failed")]))
    decision = router.route_task("Give a general answer", states=provider_states())
    result = router.ask_task("Give a general answer", decision=decision)
    entries = json.loads(log_path.read_text(encoding="utf-8"))
    assert result["status"] == "LOCAL_MODEL_REQUEST_FAILED"
    assert entries[-1]["status"] == "LOCAL_MODEL_REQUEST_FAILED"


def test_ollama_payload_enforces_route_token_limit(tmp_path, monkeypatch):
    import hermes_model_router as router

    monkeypatch.setattr(router, "LOG_PATH", tmp_path / "router.json")
    opener = SequencedOpener([{"message": {"content": "short"}}])
    monkeypatch.setattr(router, "LOCAL_OPENER", opener)
    states = provider_states(lm_online=False)
    decision = router.route_task("Compress this task", states=states)
    router.ask_task("Compress this task", decision=decision)
    payload = json.loads(opener.requests[0][0].data.decode("utf-8"))
    assert payload["options"]["num_predict"] == 256


def test_remote_provider_url_is_rejected():
    from hermes_model_router import validate_provider_url

    with pytest.raises(ValueError, match="Refusing"):
        validate_provider_url("https://api.openai.com/v1", {"cloud_enabled": False})
    with pytest.raises(ValueError, match="Refusing"):
        validate_provider_url("http://192.168.1.5:11434/api", {"cloud_enabled": False})


def test_local_opener_disables_proxies_and_redirects(monkeypatch):
    import hermes_model_router as router

    monkeypatch.setenv("HTTP_PROXY", "http://remote.invalid:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://remote.invalid:8080")
    opener = router.make_local_opener()
    proxy_handlers = [handler for handler in opener.handlers if isinstance(handler, ProxyHandler)]
    assert proxy_handlers == []
    assert any(type(handler).__name__ == "NoRedirectHandler" for handler in opener.handlers)


def test_route_decision_is_logged(tmp_path, monkeypatch):
    import hermes_model_router as router

    log_path = tmp_path / "router.json"
    monkeypatch.setattr(router, "LOG_PATH", log_path)
    router.route_task("Fix Python", states=provider_states())
    entries = json.loads(log_path.read_text(encoding="utf-8"))
    assert entries[-1]["route"] == "coding"
    assert entries[-1]["provider"] == "lm_studio"


def test_employee_router_cli_reports_status():
    env = os.environ.copy()
    env["LM_STUDIO_BASE_URL"] = "http://127.0.0.1:9/v1"
    completed = subprocess.run(
        [sys.executable, "hermes_employee.py", "router"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
        timeout=20,
    )
    assert "local_only: true" in completed.stdout.lower()
    assert "lm studio: offline" in completed.stdout.lower()


def test_safe_task_result_uses_router_planning_response(monkeypatch):
    import hermes_employee
    import hermes_model_router

    monkeypatch.setattr(
        hermes_model_router,
        "ask_task",
        lambda text: {"response": "Use the selected local plan.", "provider": "lm_studio", "model": "local-test"},
    )
    result = hermes_employee.safe_task_result({"text": "Plan a harmless note"})
    assert "Use the selected local plan." in result
    assert "lm_studio/local-test" in result


def test_refraction_compresses_whitespace_and_bounds_input():
    from hermes_refraction import compress_task

    result = compress_task("  first   second\n" + ("x" * 2000))
    assert result.startswith("first second ")
    assert len(result) <= 1200


def test_high_risk_tick_does_not_call_model_router(monkeypatch):
    import hermes_employee

    task = {"id": "TASK-HIGH", "text": "Delete a secret key", "status": "new"}
    monkeypatch.setattr(hermes_employee, "ensure_initial_files", lambda: None)
    monkeypatch.setattr(hermes_employee, "update_heartbeat", lambda *_args: None)
    monkeypatch.setattr(hermes_employee, "load_tasks", lambda: [task])
    monkeypatch.setattr(hermes_employee, "load_score", lambda: {"blocked_unsafe_tasks": 0, "proposals_created": 0})
    monkeypatch.setattr(hermes_employee, "save_score", lambda *_args: None)
    monkeypatch.setattr(hermes_employee, "save_tasks", lambda *_args: None)
    monkeypatch.setattr(hermes_employee, "add_approval", lambda *_args: None)
    monkeypatch.setattr(hermes_employee, "append_log", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(hermes_employee, "safe_task_result", lambda *_args: pytest.fail("router crossed approval gate"))
    assert hermes_employee.run_tick().startswith("PROPOSED/HIGH-RISK")
