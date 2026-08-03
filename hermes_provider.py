"""Single source of truth for Hermes model-provider policy."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "lm_studio.json"
DEFAULT_BASE_URL = "http://127.0.0.1:1234/v1"


def load_lm_studio_config() -> dict[str, Any]:
    with CONFIG_PATH.open(encoding="utf-8") as handle:
        config = json.load(handle)
    if config.get("provider") != "lm_studio" or not config.get("enabled", False):
        raise ValueError("LM Studio provider is missing or disabled")
    return config


def get_model_provider() -> str:
    return os.getenv("HERMES_MODEL_PROVIDER", "lm_studio").strip() or "lm_studio"


def is_local_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and (parsed.hostname or "").lower() in {
            "127.0.0.1",
            "localhost",
            "::1",
        }
    except (TypeError, ValueError):
        return False


def _cloud_enabled() -> bool:
    return os.getenv("HERMES_CLOUD_ENABLED", "false").strip().lower() == "true"


def _validate_url(url: str, config: dict[str, Any]) -> str:
    clean = url.strip().rstrip("/")
    host = (urlparse(clean).hostname or "").lower()
    if host == "api.openai.com" and not _cloud_enabled():
        raise ValueError("Refusing api.openai.com while HERMES_CLOUD_ENABLED is not true")
    allowed_remote = {str(item).rstrip("/") for item in config.get("allowed_remote_urls", [])}
    if not is_local_url(clean) and clean not in allowed_remote:
        raise ValueError(f"Refusing non-local LM Studio URL: {clean}")
    return clean


def validate_provider_url(url: str, *, cloud_enabled: bool = False, allowed_remote_urls: list[str] | None = None) -> str:
    """Apply Hermes' shared local-provider URL policy."""
    clean = str(url).strip().rstrip("/")
    host = (urlparse(clean).hostname or "").lower()
    allowed = {str(item).strip().rstrip("/") for item in (allowed_remote_urls or [])}
    if host == "api.openai.com" and not cloud_enabled:
        raise ValueError("Refusing api.openai.com while cloud is disabled")
    if not is_local_url(clean) and clean not in allowed:
        raise ValueError(f"Refusing non-local provider URL: {clean}")
    return clean


def get_lm_studio_base_url() -> str:
    config = load_lm_studio_config()
    candidate = os.getenv("LM_STUDIO_BASE_URL") or config.get("base_url") or DEFAULT_BASE_URL
    return _validate_url(str(candidate), config)


def _candidate_urls(config: dict[str, Any]) -> list[str]:
    override = os.getenv("LM_STUDIO_BASE_URL")
    raw_urls = [override] if override else [config.get("base_url", DEFAULT_BASE_URL), *config.get("fallback_urls", [])]
    urls: list[str] = []
    for raw_url in raw_urls:
        url = _validate_url(str(raw_url), config)
        if url not in urls:
            urls.append(url)
    return urls


def lm_studio_healthcheck() -> dict[str, Any]:
    try:
        config = load_lm_studio_config()
        if not config.get("healthcheck_enabled", True):
            return {"status": "MISCONFIGURED", "online": False, "detail": "Healthcheck is disabled", "base_url": None}
        api_key = os.getenv(str(config.get("api_key_env", "LM_STUDIO_API_KEY")), str(config.get("api_key_default", "lm-studio")))
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        endpoint = str(config.get("models_endpoint", "/models"))
        timeout = int(config.get("timeout_seconds", 20))
        errors: list[str] = []
        for base_url in _candidate_urls(config):
            try:
                request = Request(f"{base_url}{endpoint}", headers=headers, method="GET")
                with urlopen(request, timeout=timeout) as response:
                    if 200 <= response.status < 300:
                        return {"status": "ONLINE", "online": True, "detail": "LM Studio models endpoint responded", "base_url": base_url}
                    errors.append(f"{base_url}: HTTP {response.status}")
            except (HTTPError, URLError, OSError, TimeoutError) as exc:
                errors.append(f"{base_url}: {exc}")
        return {"status": "OFFLINE", "online": False, "detail": "; ".join(errors), "base_url": get_lm_studio_base_url()}
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return {"status": "MISCONFIGURED", "online": False, "detail": str(exc), "base_url": None}


def print_provider_status() -> dict[str, Any]:
    config = load_lm_studio_config()
    health = lm_studio_healthcheck()
    status = {
        "provider": get_model_provider(),
        "base_url": get_lm_studio_base_url(),
        "local_only": bool(config.get("local_only", True)),
        "lm_studio": health["status"].lower(),
        "cloud_enabled": _cloud_enabled(),
    }
    for key, value in status.items():
        print(f"{key}: {str(value).lower() if isinstance(value, bool) else value}")
    return status
