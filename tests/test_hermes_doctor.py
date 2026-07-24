from __future__ import annotations

from scripts import hermes_doctor


def test_headers_omit_placeholder_local_key(monkeypatch) -> None:
    monkeypatch.delenv("LM_STUDIO_API_TOKEN", raising=False)
    monkeypatch.delenv("LM_API_TOKEN", raising=False)

    headers = hermes_doctor._headers_for(
        {
            "env_key": "LM_STUDIO_API_TOKEN",
            "api_key": "lm-studio",
        }
    )

    assert "Authorization" not in headers


def test_headers_accept_lm_api_token_alias(monkeypatch) -> None:
    monkeypatch.delenv("LM_STUDIO_API_TOKEN", raising=False)
    monkeypatch.setenv("LM_API_TOKEN", "local-test-token")

    headers = hermes_doctor._headers_for({"env_key": "LM_STUDIO_API_TOKEN"})

    assert headers["Authorization"] == "Bearer local-test-token"


def test_resolve_runtime_uses_configured_provider() -> None:
    name, provider = hermes_doctor.resolve_runtime(
        {
            "hermes": {"default_runtime": "lmstudio_windows"},
            "providers": {
                "lmstudio_windows": {
                    "base_url": "http://127.0.0.1:1234/v1",
                }
            },
        }
    )

    assert name == "lmstudio_windows"
    assert provider["base_url"] == "http://127.0.0.1:1234/v1"


def test_existing_hermes_requires_expected_health_payload(monkeypatch) -> None:
    monkeypatch.setattr(
        hermes_doctor,
        "_get_json",
        lambda *_args, **_kwargs: {"status": "ok", "service": "hermes"},
    )

    assert hermes_doctor.check_existing_hermes("127.0.0.1", 8000) is True
