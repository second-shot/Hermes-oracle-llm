#!/usr/bin/env python3
"""Integration checks for Hermes local-first core functionality."""

import json
import pytest
from llm.client import call_model


def load_config():
    with open("config.json") as f:
        return json.load(f)


def test_hermes_integration_stays_local_without_provider_runtime(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_LLM_PROVIDER", raising=False)

    config = load_config()
    provider = config["llm"]["provider"]
    model = config["llm"]["model"]

    assert provider == "local_router"
    assert model == "hermes-free"
    assert config["cloud_enabled"] is False

    test_prompt = {
        "task": {
            "goal": "Test workflow creation",
            "task_type": "text_reasoning",
            "compressed_prompt": "Create a simple test workflow",
        }
    }

    result = call_model(test_prompt, "local", config)

    assert result["meta"]["mode"] == "stub"
    assert result["meta"]["provider"] == "stub"
    assert "reason" in result["meta"]
    assert "local_router" in result["meta"]["reason"]


if __name__ == "__main__":
    print("Running Hermes integration check")
    config = load_config()
    test_prompt = {
        "task": {
            "goal": "Test workflow creation",
            "task_type": "text_reasoning",
            "compressed_prompt": "Create a simple test workflow",
        }
    }
    result = call_model(test_prompt, "local", config)
    print(result)
