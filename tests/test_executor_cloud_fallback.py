from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import core.executor as executor


class _RouterReturnsLocalMissing:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    def run_task(self, *_args, **_kwargs):
        return {
            "error": "local-runtime-missing",
            "message": "Local models were selected first, but no local model completed the task.",
        }


def test_execute_task_never_silently_falls_back_to_cloud(monkeypatch) -> None:
    monkeypatch.setattr(executor, "compress", lambda user_input: {"goal": user_input})
    monkeypatch.setattr(executor, "read_memory", lambda _compressed: {})
    monkeypatch.setattr(executor, "update_memory", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(executor, "ModelRouter", _RouterReturnsLocalMissing)

    calls: list[tuple[dict, str, dict]] = []

    def fake_call_model(prompt, route, config):
        calls.append((prompt, route, config))
        return {"result": "cloud fallback reply", "meta": {"mode": "openai", "provider": "openai"}}

    monkeypatch.setattr(executor, "call_model", fake_call_model)

    result = executor.execute_task(
        "Say Hermes is ready.",
        {
            "cloud_enabled": True,
            "llm": {"provider": "openai", "model": "gpt-4"},
        },
    )

    assert result["error"] == "local-runtime-missing"
    assert calls == []


def test_execute_task_keeps_local_runtime_error_when_cloud_disabled(monkeypatch) -> None:
    monkeypatch.setattr(executor, "compress", lambda user_input: {"goal": user_input})
    monkeypatch.setattr(executor, "read_memory", lambda _compressed: {})
    monkeypatch.setattr(executor, "update_memory", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(executor, "ModelRouter", _RouterReturnsLocalMissing)
    monkeypatch.setattr(executor, "call_model", lambda *_args, **_kwargs: {"result": "should not be used"})

    result = executor.execute_task(
        "Say Hermes is ready.",
        {
            "cloud_enabled": False,
            "llm": {"provider": "openai", "model": "gpt-4"},
        },
    )

    assert result["error"] == "local-runtime-missing"
