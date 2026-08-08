from __future__ import annotations

from core import executor


def test_execute_task_preserves_raw_simple_chat_and_skips_memory(monkeypatch):
    captured = {}

    class FakeRouter:
        def __init__(self, memory_reader):
            self.memory_reader = memory_reader

        def run_task(self, user_input, infer, runtime_config=None):
            plan = {"task_route": "simple_chat"}
            captured["memory"] = self.memory_reader(plan)
            return {
                "source": "model",
                **infer(
                    {
                        "provider": {"name": "ollama", "provider": {"base_url": "http://127.0.0.1:11434"}},
                        "model": "llama3.2:3b",
                        "task_route": "simple_chat",
                        "params": {},
                        "memory": captured["memory"],
                        "repo_index": None,
                    }
                ),
            }

    def fake_call_model(prompt, route, config):
        captured["prompt"] = prompt
        return {"result": "ORANGE FALCON 5531", "meta": {"mode": "local", "provider": "ollama", "model": route["model"]}}

    monkeypatch.setattr(executor, "ModelRouter", FakeRouter)
    monkeypatch.setattr(executor, "call_model", fake_call_model)
    monkeypatch.setattr(executor, "read_memory", lambda _compressed: {"poisoned": "stale output"})
    monkeypatch.setattr(executor, "update_memory", lambda *_args, **_kwargs: None)

    result = executor.execute_task(
        "Reply with exactly: ORANGE FALCON 5531",
        {"cloud_enabled": False},
    )

    assert captured["memory"] == {}
    assert captured["prompt"]["task"]["compressed_prompt"] == "Reply with exactly: ORANGE FALCON 5531"
    assert "T:text_reasoning" not in captured["prompt"]["task"]["compressed_prompt"]
    assert result["result"] == "ORANGE FALCON 5531"
