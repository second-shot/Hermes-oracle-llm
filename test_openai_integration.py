#!/usr/bin/env python
"""Integration checks for Hermes local-first provider defaults."""

import json
import os
from llm.client import call_model


def load_config():
    with open("config.json", "r") as f:
        return json.load(f)


def test_openai_bridge_is_not_the_default(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_LLM_PROVIDER", raising=False)

    config = load_config()

    assert config["cloud_enabled"] is False
    assert config["llm"]["provider"] == "stub"
    assert config["llm"]["model"] == "hermes-local"

    prompt = {"task": {"goal": "Test workflow creation", "task_type": "text_reasoning"}}
    result = call_model(prompt, "local", config)

    assert isinstance(result, dict)
    assert result["meta"]["mode"] == "stub"
    assert result["meta"]["provider"] == "stub"
    assert "reason" in result["meta"]
    assert "no model provider configured" in result["meta"]["reason"]


if __name__ == "__main__":
    print("Running Hermes OpenAI integration check")
    config = load_config()
    prompt = {"task": {"goal": "Test workflow creation", "task_type": "text_reasoning"}}
    result = call_model(prompt, "local", config)
    print(result)
