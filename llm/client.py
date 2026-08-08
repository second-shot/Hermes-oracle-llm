import os
import json
import socket
import urllib.error
import urllib.request
from dotenv import load_dotenv
from openai import OpenAI, APIError

# Load environment variables from a .env file if present
load_dotenv()


DEFAULT_PROVIDER = "stub"
PLACEHOLDER_LOCAL_API_KEYS = {
    "",
    "<redacted>",
    "lm-studio",
    "local",
    "placeholder",
    "changeme",
    "none",
}
DEFAULT_LOCAL_DISCOVERY_TIMEOUT_SECONDS = 20
DEFAULT_LOCAL_INFERENCE_TIMEOUT_SECONDS = 120
DEFAULT_REMOTE_TIMEOUT_SECONDS = 60


def _error_result(provider_name, reason, retryable=True, cooldown_seconds=300):
    return {
        "error": "provider-failure",
        "failure_reason": reason,
        "retryable": retryable,
        "cooldown_seconds": cooldown_seconds,
        "meta": {"provider": provider_name},
    }


def _provider(config):
    return (
        os.environ.get("HERMES_LLM_PROVIDER")
        or config.get("llm", {}).get("provider")
        or DEFAULT_PROVIDER
    ).lower()


def _compressed_task(prompt):
    task = prompt.get("task", {}) if isinstance(prompt, dict) else {}
    return {
        "goal": task.get("goal", ""),
        "task_type": task.get("task_type", "unknown"),
        "compressed_prompt": task.get("compressed_prompt", ""),
        "entities": task.get("entities", []),
        "constraints": task.get("constraints", []),
    }


def _stub_response(prompt, reason="no model provider configured"):
    task = _compressed_task(prompt)
    goal = task["goal"].strip()

    if goal.lower().startswith("task: create first resale workflow"):
        result = (
            "HERMES STUB MODE\n"
            "Workflow: first resale workflow\n\n"
            "1. CAPTURE: photograph item front, back, label, damage, size, material.\n"
            "2. CLASSIFY: category, brand, condition, resale platform.\n"
            "3. PRICE: low / fair / stretch price.\n"
            "4. ROUTE: quick-sale items to Vinted, higher-value items to eBay, rare/designer to research queue.\n"
            "5. LIST: title, 5 bullet description, condition note, price, shipping status.\n"
            "6. DECIDE: NOW if value is clear, PREP if needs cleaning/photos, HOLD if value unknown, EXIT if not worth time.\n"
            "7. LOG: save item, price, platform, next action, and result."
        )
    else:
        result = (
            "HERMES STUB MODE\n"
            f"Reason: {reason}\n"
            f"Task type: {task['task_type']}\n"
            f"Goal: {task['goal']}\n"
            f"Compressed input: {task['compressed_prompt']}\n\n"
            "No external LLM is active. Hermes is running routing, memory, cache, and deterministic fallback logic."
        )

    return {
        "result": result,
        "meta": {
            "mode": "stub",
            "reason": reason,
            "provider": "stub",
        },
    }


def _local_runtime_response(prompt, provider_name, model_name):
    return _stub_response(
        prompt,
        f"Local provider selected: {provider_name} / {model_name}. Hermes stayed offline and zero-cost.",
    )


def _messages_for_local_runtime(prompt):
    task = _compressed_task(prompt)
    user_content = task.get("compressed_prompt") or task.get("goal") or "Help with the current task."

    # Plain conversational chat must preserve the user's text exactly. Small
    # local models can overreact to extra system framing or compressed control
    # packets, so simple chat intentionally uses only the raw user message.
    if isinstance(prompt, dict) and prompt.get("raw_chat"):
        return [{"role": "user", "content": user_content}]

    memory = prompt.get("memory", {}) if isinstance(prompt, dict) else {}
    memory_text = ""
    if memory:
        memory_text = f"\nRelevant memory/context:\n{json.dumps(memory, ensure_ascii=False)[:1200]}"
    return [
        {
            "role": "system",
            "content": "You are Hermes running in local-first mode. Prefer concise, actionable answers and avoid unsafe or unverified actions.",
        },
        {
            "role": "user",
            "content": f"{user_content}{memory_text}",
        },
    ]


def _provider_api_token(provider_config):
    env_key = str(provider_config.get("env_key", "")).strip()
    if env_key:
        env_value = os.environ.get(env_key, "").strip()
        if env_value:
            return env_value
        if env_key == "LM_STUDIO_API_TOKEN":
            alias_value = os.environ.get("LM_API_TOKEN", "").strip()
            if alias_value:
                return alias_value

    api_key = str(provider_config.get("api_key", "")).strip()
    if api_key.lower() in PLACEHOLDER_LOCAL_API_KEYS:
        return None
    return api_key or None


def _request_json(url, headers=None, payload=None, method="GET", timeout=DEFAULT_LOCAL_DISCOVERY_TIMEOUT_SECONDS):
    encoded_payload = None
    if payload is not None:
        encoded_payload = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        url,
        data=encoded_payload,
        headers=headers or {},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _error_body(exc):
    try:
        return exc.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _classify_http_error(provider_name, exc):
    body = _error_body(exc).lower()
    if exc.code == 402:
        return _error_result(provider_name, "http_402_payment_required", retryable=True, cooldown_seconds=900)
    if exc.code == 429:
        return _error_result(provider_name, "http_429_rate_limit", retryable=True, cooldown_seconds=300)
    if exc.code in {401, 403}:
        return _error_result(provider_name, "authentication_failed", retryable=False, cooldown_seconds=300)
    if exc.code == 404:
        return _error_result(provider_name, "model_unavailable", retryable=True, cooldown_seconds=600)
    if "insufficient credits" in body:
        return _error_result(provider_name, "insufficient_credits", retryable=True, cooldown_seconds=900)
    if "exhausted quota" in body or "quota exceeded" in body:
        return _error_result(provider_name, "exhausted_quota", retryable=True, cooldown_seconds=900)
    if exc.code >= 500:
        return _error_result(provider_name, "provider_unavailable", retryable=True, cooldown_seconds=300)
    return _error_result(provider_name, f"http_{exc.code}", retryable=True, cooldown_seconds=300)


def _classify_transport_error(provider_name, exc):
    message = str(exc).lower()
    if isinstance(exc, TimeoutError) or isinstance(exc, socket.timeout) or "timed out" in message:
        return _error_result(provider_name, "timeout", retryable=True, cooldown_seconds=300)
    if "unavailable" in message:
        return _error_result(provider_name, "provider_unavailable", retryable=True, cooldown_seconds=300)
    return _error_result(provider_name, "connection_failure", retryable=True, cooldown_seconds=120)


def _discover_local_model(base_url, headers, requested_model, timeout=DEFAULT_LOCAL_DISCOVERY_TIMEOUT_SECONDS):
    try:
        body = _request_json(f"{base_url}/models", headers=headers, method="GET", timeout=timeout)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return requested_model

    available = []
    for item in body.get("data", []):
        if isinstance(item, dict) and item.get("id"):
            available.append(item["id"])

    if requested_model in available:
        return requested_model
    if available:
        return available[0]
    return requested_model


def _openai_compatible_local_response(prompt, provider_name, provider_config, model_name, params):
    base_url = str(provider_config.get("base_url", "")).rstrip("/")
    if not base_url:
        return None

    headers = {"Content-Type": "application/json"}
    api_token = _provider_api_token(provider_config)
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"

    discovery_timeout = int(provider_config.get("model_discovery_timeout_seconds", DEFAULT_LOCAL_DISCOVERY_TIMEOUT_SECONDS))
    inference_timeout = int(provider_config.get("request_timeout_seconds", DEFAULT_LOCAL_INFERENCE_TIMEOUT_SECONDS))

    resolved_model_name = _discover_local_model(base_url, headers, model_name, timeout=discovery_timeout)
    payload = {
        "model": resolved_model_name,
        "messages": _messages_for_local_runtime(prompt),
        "temperature": params.get("temperature", 0.2),
        "top_p": params.get("top_p", 0.8),
        "max_tokens": params.get("max_tokens", 512),
    }
    try:
        body = _request_json(
            f"{base_url}/chat/completions",
            headers=headers,
            payload=payload,
            method="POST",
            timeout=inference_timeout,
        )
    except urllib.error.HTTPError as exc:
        return _classify_http_error(provider_name, exc)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return _classify_transport_error(provider_name, exc)

    try:
        result = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return _error_result(provider_name, "provider_unavailable", retryable=True, cooldown_seconds=300)

    return {
        "result": result,
        "meta": {
            "mode": "local",
            "provider": provider_name,
            "model": resolved_model_name,
        },
    }


def _mlx_response(prompt, config):
    return _stub_response(
        prompt,
        "MLX provider selected but not implemented yet. Add mlx-lm runtime when ready.",
    )


def _openrouter_response(prompt, config):
    return _stub_response(
        prompt,
        "OpenRouter provider selected but not implemented yet. Add API client and key when ready.",
    )


def _ollama_response(prompt, config):
    return _stub_response(
        prompt,
        "Ollama provider selected but not implemented yet. Add local HTTP client when ready.",
    )


def _openai_response(prompt, config):
    try:
        api_key = (
            config.get("llm", {}).get("api_key")
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("HERMES_OPENAI_API_KEY")
        )

        if not api_key:
            return _stub_response(
                prompt,
                "OpenAI provider selected but no API key configured. Set 'llm.api_key' in config.json or the OPENAI_API_KEY environment variable (or add a .env file).",
            )

        client = OpenAI(api_key=api_key)
        task = _compressed_task(prompt)
        messages = [
            {
                "role": "system",
                "content": "You are Hermes, an intelligent task routing and automation system. Provide clear, actionable responses."
            },
            {
                "role": "user",
                "content": task.get("compressed_prompt", task.get("goal", ""))
            }
        ]

        model = config.get("llm", {}).get("model", "gpt-4")
        temperature = config.get("llm", {}).get("temperature", 0.7)

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=config.get("limits", {}).get("max_tokens", {}).get("text_reasoning", 100),
        )

        result = response.choices[0].message.content

        return {
            "result": result,
            "meta": {
                "mode": "openai",
                "provider": "openai",
                "model": model,
                "tokens_used": response.usage.total_tokens,
            },
        }

    except APIError as e:
        return _stub_response(prompt, f"OpenAI API error: {str(e)}")
    except Exception as e:
        return _stub_response(prompt, f"OpenAI integration error: {str(e)}")


def _openai_compatible_remote_response(prompt, provider_name, provider_config, model_name, params):
    base_url = str(provider_config.get("base_url", "")).rstrip("/")
    api_token = _provider_api_token(provider_config)
    if not api_token:
        return _error_result(provider_name, "authentication_failed", retryable=False, cooldown_seconds=300)

    payload = {
        "model": model_name,
        "messages": _messages_for_local_runtime(prompt),
        "temperature": params.get("temperature", 0.2),
        "top_p": params.get("top_p", 0.8),
        "max_tokens": params.get("max_tokens", 512),
    }
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_token}"}
    try:
        body = _request_json(
            f"{base_url}/chat/completions",
            headers=headers,
            payload=payload,
            method="POST",
            timeout=int(provider_config.get("request_timeout_seconds", DEFAULT_REMOTE_TIMEOUT_SECONDS)),
        )
    except urllib.error.HTTPError as exc:
        return _classify_http_error(provider_name, exc)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return _classify_transport_error(provider_name, exc)

    try:
        result = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return _error_result(provider_name, "provider_unavailable", retryable=True, cooldown_seconds=300)

    return {
        "result": result,
        "meta": {
            "mode": "remote",
            "provider": provider_name,
            "model": model_name,
        },
    }


def _ollama_native_response(prompt, provider_name, provider_config, model_name, params):
    base_url = str(provider_config.get("base_url", "http://127.0.0.1:11434")).rstrip("/")
    payload = {
        "model": model_name,
        "messages": _messages_for_local_runtime(prompt),
        "stream": False,
        "options": {
            "temperature": params.get("temperature", 0.2),
            "num_predict": params.get("max_tokens", 512),
        },
    }
    try:
        body = _request_json(
            f"{base_url}/api/chat",
            headers={"Content-Type": "application/json"},
            payload=payload,
            method="POST",
            timeout=int(provider_config.get("request_timeout_seconds", DEFAULT_REMOTE_TIMEOUT_SECONDS)),
        )
    except urllib.error.HTTPError as exc:
        return _classify_http_error(provider_name, exc)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return _classify_transport_error(provider_name, exc)

    try:
        result = body["message"]["content"]
    except (KeyError, TypeError):
        return _error_result(provider_name, "provider_unavailable", retryable=True, cooldown_seconds=300)

    return {
        "result": result,
        "meta": {
            "mode": "local",
            "provider": provider_name,
            "model": model_name,
        },
    }


def call_model(prompt, route, config):
    if isinstance(route, dict):
        provider_name = route.get("provider", "stub")
        provider_config = route.get("provider_config", {})
        model_name = route.get("model", "unknown-model")
        params = route.get("params", {})
        if route.get("kind") not in {"local", "provider"}:
            return _stub_response(prompt, f"route '{route}' is not implemented")
        if provider_name in {"lmstudio_windows", "llama_cpp_server"}:
            return _openai_compatible_local_response(prompt, provider_name, provider_config, model_name, params)
        if provider_name == "ollama":
            return _ollama_native_response(prompt, provider_name, provider_config, model_name, params)
        if provider_name == "mlx_mac":
            return _mlx_response(prompt, config)
        if provider_name == "openrouter_free":
            return _openai_compatible_remote_response(prompt, provider_name, provider_config, model_name, params)
        return _stub_response(prompt, f"provider '{provider_name}' is not implemented")

    provider = _provider(config)
    if provider == "openai":
        return _openai_response(prompt, config)
    if provider == "mlx":
        return _mlx_response(prompt, config)
    if provider == "openrouter":
        return _openrouter_response(prompt, config)
    if provider == "ollama":
        return _ollama_response(prompt, config)
    if provider in {"local", "local_router", "lmstudio", "lm_studio"}:
        return _local_runtime_response(prompt, provider, config.get("llm", {}).get("model", "local-model"))
    return _stub_response(prompt)
