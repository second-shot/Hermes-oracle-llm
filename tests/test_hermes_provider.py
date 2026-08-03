import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_local_url_policy_accepts_loopback_and_rejects_remote():
    from hermes_provider import is_local_url

    assert is_local_url("http://127.0.0.1:1234/v1")
    assert is_local_url("http://localhost:1234/v1")
    assert not is_local_url("https://api.openai.com/v1")
    assert not is_local_url("http://192.168.1.20:1234/v1")


def test_checked_in_config_is_local_lm_studio():
    from hermes_provider import load_lm_studio_config

    config = load_lm_studio_config()
    assert config["provider"] == "lm_studio"
    assert config["local_only"] is True
    assert config["base_url"] == "http://127.0.0.1:1234/v1"
    assert "http://localhost:1234/v1" in config["fallback_urls"]


def test_remote_environment_override_is_rejected(monkeypatch):
    from hermes_provider import get_lm_studio_base_url

    monkeypatch.setenv("LM_STUDIO_BASE_URL", "https://api.openai.com/v1")
    with pytest.raises(ValueError, match="Refusing"):
        get_lm_studio_base_url()


def test_healthcheck_returns_offline_without_raising(monkeypatch):
    import hermes_provider

    def fail(*_args, **_kwargs):
        raise OSError("not listening")

    monkeypatch.setattr(hermes_provider, "urlopen", fail)
    result = hermes_provider.lm_studio_healthcheck()
    assert result["status"] == "OFFLINE"
    assert result["online"] is False
    assert "not listening" in result["detail"]


def test_provider_cli_reports_local_policy():
    env = os.environ.copy()
    env.pop("LM_STUDIO_BASE_URL", None)
    completed = subprocess.run(
        [sys.executable, "hermes_employee.py", "provider"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    output = completed.stdout.lower()
    assert "provider: lm_studio" in output
    assert "base_url: http://127.0.0.1:1234/v1" in output
    assert "local_only: true" in output
    assert "cloud_enabled: false" in output


def test_lm_studio_config_has_no_markdown_links():
    config = json.loads((ROOT / "config" / "lm_studio.json").read_text(encoding="utf-8"))
    assert "[http" not in json.dumps(config)


def test_existing_runtime_configs_use_primary_loopback_url():
    local_model = json.loads((ROOT / "config" / "local_model.json").read_text(encoding="utf-8"))
    rotation = (ROOT / "config" / "hermes.model.rotation.yaml").read_text(encoding="utf-8")
    assert local_model["api_base"] == "http://127.0.0.1:1234/v1"
    assert 'base_url: "http://127.0.0.1:1234/v1"' in rotation
