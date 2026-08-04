#!/usr/bin/env python
"""Regression check that the default Hermes path does not select OpenAI."""

import json
from llm.client import call_model


def load_config():
    with open("config.json", "r") as f:
        return json.load(f)


def test_default_integration_does_not_select_openai(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_LLM_PROVIDER", raising=False)

    config = load_config()

    assert config["llm"]["provider"] == "local_router"
    assert config["llm"]["model"] == "hermes-free"
    assert config["cloud_enabled"] is False

    prompt = {"task": {"goal": "Test workflow creation", "task_type": "text_reasoning"}}
    result = call_model(prompt, "local", config)

    assert isinstance(result, dict)
    assert result["meta"]["mode"] == "stub"
    assert result["meta"]["provider"] == "stub"
    assert "reason" in result["meta"]
    assert "local_router" in result["meta"]["reason"]


if __name__ == "__main__":
    print("Running Hermes local-first integration check")
    config = load_config()
    prompt = {"task": {"goal": "Test workflow creation", "task_type": "text_reasoning"}}
    result = call_model(prompt, "local", config)
    print(result)
