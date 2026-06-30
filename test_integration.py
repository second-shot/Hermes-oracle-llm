#!/usr/bin/env python3
"""Integration checks for Hermes core functionality."""

from llm.client import call_model
from main import load_config


def test_hermes_integration_stub_mode(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("HERMES_LLM_PROVIDER", raising=False)

    config = load_config()

    assert config["cloud_enabled"] is False
    assert config["llm"]["provider"] == "stub"
    assert config["llm"]["model"] == "stub"

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
    assert result["meta"]["reason"] == "no model provider configured"


def test_load_config_uses_repo_root(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    config = load_config()

    assert config["cloud_enabled"] is False
    assert config["llm"]["provider"] == "stub"


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
