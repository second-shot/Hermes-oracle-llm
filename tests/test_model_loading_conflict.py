from __future__ import annotations

from backend.routes import llm


def test_legacy_config_matches_local_first_policy() -> None:
    config = llm.load_config()

    assert config["cloud_enabled"] is False
    assert config["primary_model"] == "fast_chat"
    assert config["llm"]["provider"] == "local_router"
    assert config["llm"]["model"] == "auto"
    assert set(config["routing"].values()) == {"local"}


def test_chat_rejects_overlapping_local_model_request() -> None:
    assert llm._EXECUTOR_LOCK.acquire(blocking=False)
    try:
        response = llm.chat_completion(
            {
                "model": "hermes-local",
                "messages": [{"role": "user", "content": "Start another model request."}],
            }
        )
    finally:
        llm._EXECUTOR_LOCK.release()

    content = response["choices"][0]["message"]["content"]
    assert "already processing a local model request" in content


def test_executor_lock_is_released_after_completed_request(monkeypatch) -> None:
    monkeypatch.setattr(llm, "execute_task", lambda *_args, **_kwargs: {"result": "ready"})

    response = llm.chat_completion(
        {
            "model": "hermes-local",
            "messages": [{"role": "user", "content": "Say ready."}],
        }
    )

    assert response["choices"][0]["message"]["content"] == "ready"
    assert llm._EXECUTOR_LOCK.locked() is False
