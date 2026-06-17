#!/usr/bin/env python
"""Integration checks for Hermes OpenAI support."""

import json
import os
from llm.client import call_model


def load_config():
    with open("config.json", "r") as f:
        return json.load(f)


def test_openai_integration_stub_mode(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_LLM_PROVIDER", raising=False)

    config = load_config()

    assert config["llm"]["provider"] == "openai"
    assert config["llm"]["model"] == "gpt-4"

    prompt = {"task": {"goal": "Test workflow creation", "task_type": "text_reasoning"}}
    result = call_model(prompt, "local", config)

    assert isinstance(result, dict)
    assert result["meta"]["mode"] == "stub"
    assert result["meta"]["provider"] == "stub"
    assert "reason" in result["meta"]
    assert "OpenAI provider selected" in result["meta"]["reason"]


if __name__ == "__main__":
    print("Running Hermes OpenAI integration check")
    config = load_config()
    prompt = {"task": {"goal": "Test workflow creation", "task_type": "text_reasoning"}}
    result = call_model(prompt, "local", config)
    print(result)
