#!/usr/bin/env python
"""Integration checks for Hermes OpenAI support."""

from llm.client import call_model
from main import load_config


def test_openai_integration_stub_mode(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("HERMES_LLM_PROVIDER", "openai")

    config = load_config()

    assert config["llm"]["provider"] == "stub"
    assert config["llm"]["model"] == "stub"

    prompt = {"task": {"goal": "Test workflow creation", "task_type": "text_reasoning"}}
    result = call_model(prompt, "local", config)

    assert isinstance(result, dict)
    assert result["meta"]["mode"] == "stub"
    assert result["meta"]["provider"] == "stub"
    assert "OpenAI provider selected but no API key configured" in result["meta"]["reason"]


if __name__ == "__main__":
    print("Running Hermes OpenAI integration check")
    config = load_config()
    prompt = {"task": {"goal": "Test workflow creation", "task_type": "text_reasoning"}}
    result = call_model(prompt, "local", config)
    print(result)
