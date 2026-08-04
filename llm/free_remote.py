from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any


DEFAULT_DISCOVERY_TIMEOUT_SECONDS = 20
DEFAULT_INFERENCE_TIMEOUT_SECONDS = 120


def _messages(prompt: dict[str, Any]) -> list[dict[str, str]]:
    task = prompt.get("task", {}) if isinstance(prompt, dict) else {}
    memory = prompt.get("memory", {}) if isinstance(prompt, dict) else {}
    user_content = task.get("compressed_prompt") or task.get("goal") or "Help with the current task."
    if memory:
        user_content += f"\nRelevant memory/context:\n{json.dumps(memory, ensure_ascii=False)[:1200]}"
    return [
        {
            "role": "system",
            "content": "You are Hermes. Give concise, actionable answers. Never claim a paid model was used.",
        },
        {"role": "user", "content": user_content},
    ]


def _request_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any] | None = None,
    method: str = "GET",
    timeout: int = DEFAULT_DISCOVERY_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def call_free_remote(
    prompt: dict[str, Any],
    provider_name: str,
    provider_config: dict[str, Any],
    model_name: str,
    params: dict[str, Any],
) -> dict[str, Any] | None:
    if not (
        provider_config.get("explicit_opt_in") is True
        and provider_config.get("verified_zero_cost") is True
        and provider_config.get("free_model_only") is True
        and provider_config.get("cost") in {0, "0", "free"}
    ):
        return None

    base_url = str(provider_config.get("base_url", "")).strip().rstrip("/")
    if not base_url.lower().startswith("https://"):
        return None

    env_key = str(provider_config.get("env_key", "HERMES_FREE_REMOTE_API_KEY")).strip()
    token = os.environ.get(env_key, "").strip() if env_key else ""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    payload = {
        "model": model_name,
        "messages": _messages(prompt),
        "temperature": params.get("temperature", 0.2),
        "top_p": params.get("top_p", 0.8),
        "max_tokens": params.get("max_tokens", 512),
    }
    timeout = int(provider_config.get("request_timeout_seconds", DEFAULT_INFERENCE_TIMEOUT_SECONDS))
    try:
        body = _request_json(
            f"{base_url}/chat/completions",
            headers=headers,
            payload=payload,
            method="POST",
            timeout=timeout,
        )
        result = body["choices"][0]["message"]["content"]
    except (
        urllib.error.URLError,
        urllib.error.HTTPError,
        TimeoutError,
        json.JSONDecodeError,
        KeyError,
        IndexError,
        TypeError,
    ):
        return None

    return {
        "result": result,
        "meta": {
            "mode": "free-remote",
            "provider": provider_name,
            "model": model_name,
            "verified_zero_cost": True,
        },
    }
