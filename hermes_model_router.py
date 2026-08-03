"""Offline model router for Hermes/MIA."""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from hermes_provider import validate_provider_url as shared_validate_provider_url


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config" / "model_router.json"
LOG_PATH = ROOT / "data" / "router" / "model_router_log.json"
FALLBACK_STATUS = "NO_LOCAL_MODEL_ONLINE"


class NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def make_local_opener():
    """Create an opener that cannot use ambient proxies or follow redirects."""
    return build_opener(ProxyHandler({}), NoRedirectHandler())


LOCAL_OPENER = make_local_opener()


def load_router_config(path: str | Path = CONFIG_PATH) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        config = json.load(handle)
    if not config.get("local_only", True) and not config.get("cloud_enabled", False):
        raise ValueError("Router must be local-only while cloud is disabled")
    return config


def validate_provider_url(url: str, config: dict[str, Any]) -> str:
    return shared_validate_provider_url(
        url,
        cloud_enabled=bool(config.get("cloud_enabled", False)),
        allowed_remote_urls=list(config.get("allowed_remote_urls", [])),
    )


def classify_task(text: str) -> str:
    lowered = text.lower()
    route_terms = (
        ("security", ("security", "threat", "vulnerability", "secret scan", "harden", "ethical")),
        ("vision", ("image", "screenshot", "photo", "vision", "picture")),
        ("compress", ("compress", "summarize", "summarise", "condense", "one next move")),
        ("classify", ("classify", "categorize", "categorise", "label this")),
        ("coding", ("python", "code", "syntax", "bug", "debug", "function", "repository")),
        ("reasoning", ("reason", "architecture", "analyze", "analyse", "strategy", "plan carefully")),
    )
    for route, terms in route_terms:
        if any(term in lowered for term in terms):
            return route
    return "general"


def _provider_urls(name: str, provider: dict[str, Any], config: dict[str, Any]) -> list[str]:
    override = os.getenv("LM_STUDIO_BASE_URL") if name == "lm_studio" else os.getenv("OLLAMA_BASE_URL")
    raw = [override] if override else [provider.get("base_url"), *provider.get("fallback_urls", [])]
    urls: list[str] = []
    for item in raw:
        if item:
            clean = validate_provider_url(str(item), config)
            if clean not in urls:
                urls.append(clean)
    return urls


def _decode_models(name: str, body: dict[str, Any]) -> list[str]:
    records = body.get("data", []) if name == "lm_studio" else body.get("models", [])
    key = "id" if name == "lm_studio" else "name"
    return [str(record.get(key, "")).strip() for record in records if isinstance(record, dict) and record.get(key)]


def probe_provider(name: str, provider: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    state = {"online": False, "base_url": None, "models": [], "detail": "disabled"}
    if not provider.get("enabled", False):
        return state
    errors: list[str] = []
    endpoint = str(provider.get("models_endpoint", "/models"))
    timeout = int(provider.get("timeout_seconds", 30))
    for base_url in _provider_urls(name, provider, config):
        headers = {"Accept": "application/json"}
        if name == "lm_studio":
            api_key = os.getenv(str(provider.get("api_key_env", "LM_STUDIO_API_KEY")), str(provider.get("api_key_default", "lm-studio")))
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
        try:
            with LOCAL_OPENER.open(Request(f"{base_url}{endpoint}", headers=headers, method="GET"), timeout=timeout) as response:
                body = json.loads(response.read().decode("utf-8"))
                return {"online": True, "base_url": base_url, "models": _decode_models(name, body), "detail": "online"}
        except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError) as exc:
            errors.append(f"{base_url}: {exc}")
    state["detail"] = "; ".join(errors) or "no valid URL"
    return state


def probe_providers(config: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    config = config or load_router_config()
    return {name: probe_provider(name, provider, config) for name, provider in config.get("providers", {}).items()}


def _model_size(model: str) -> float:
    matches = re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)\s*[bB](?![A-Za-z])", model)
    return float(matches[-1]) if matches else 4.0


def _is_vision_model(model: str) -> bool:
    lowered = model.lower()
    return any(token in lowered for token in ("vision", "llava", "vl", "bakllava"))


def select_model(route: str, models: list[str], route_config: dict[str, Any]) -> str | None:
    if route == "vision":
        models = [model for model in models if _is_vision_model(model)]
    if not models:
        return None
    by_lower = {model.lower(): model for model in models}
    for preferred in route_config.get("preferred_models", []):
        if str(preferred).lower() in by_lower:
            return by_lower[str(preferred).lower()]
    if route in {"compress", "classify"}:
        return min(models, key=lambda model: (_model_size(model), model.lower()))
    return max(models, key=lambda model: (_model_size(model), model.lower()))


def _provider_order(config: dict[str, Any]) -> list[str]:
    first = [str(config.get("default_provider", "lm_studio")), str(config.get("fallback_provider", "ollama"))]
    return list(dict.fromkeys([*first, *config.get("providers", {}).keys()]))


def append_route_log(decision: dict[str, Any]) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        entries = json.loads(LOG_PATH.read_text(encoding="utf-8")) if LOG_PATH.exists() else []
        if not isinstance(entries, list):
            entries = []
    except (OSError, json.JSONDecodeError):
        entries = []
    entries.append({key: decision.get(key) for key in ("timestamp", "route", "provider", "model", "status")})
    temporary = LOG_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    temporary.replace(LOG_PATH)


def route_task(text: str, *, states: dict[str, dict[str, Any]] | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_router_config()
    states = states if states is not None else probe_providers(config)
    route = classify_task(text)
    route_config = config.get("routes", {}).get(route, {})
    decision = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "route": route,
        "provider": "deterministic",
        "model": None,
        "status": FALLBACK_STATUS,
        "base_url": None,
        "candidates": [],
        "parameters": {"max_tokens": route_config.get("max_tokens"), "temperature": route_config.get("temperature")},
    }
    any_online = False
    for name in _provider_order(config):
        state = states.get(name, {})
        if not state.get("online"):
            continue
        any_online = True
        model = select_model(route, list(state.get("models", [])), route_config)
        if model:
            candidate = {"provider": name, "model": model, "base_url": state.get("base_url")}
            decision["candidates"].append(candidate)
            if decision["model"] is None:
                decision.update(**candidate, status="LOCAL_MODEL_SELECTED")
    if any_online and decision["model"] is None:
        decision["status"] = "NO_MATCHING_LOCAL_MODEL"
    append_route_log(decision)
    return decision


def _extract_response(provider: str, body: dict[str, Any]) -> str:
    if provider == "lm_studio":
        choices = body.get("choices", [])
        if choices and isinstance(choices[0], dict):
            return str(choices[0].get("message", {}).get("content", "")).strip()
    return str(body.get("message", {}).get("content", "")).strip()


def _ask_candidate(text: str, candidate: dict[str, Any], parameters: dict[str, Any], config: dict[str, Any]) -> str:
    name = str(candidate["provider"])
    provider = config["providers"][name]
    base_url = validate_provider_url(str(candidate["base_url"]), config)
    endpoint = str(provider.get("chat_endpoint", "/chat"))
    if name == "lm_studio":
        payload = {"model": candidate["model"], "messages": [{"role": "user", "content": text}], **parameters}
        api_key = os.getenv(str(provider.get("api_key_env", "LM_STUDIO_API_KEY")), str(provider.get("api_key_default", "lm-studio")))
        headers = {"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"}
    else:
        payload = {
            "model": candidate["model"],
            "messages": [{"role": "user", "content": text}],
            "stream": False,
            "options": {"temperature": parameters.get("temperature"), "num_predict": parameters.get("max_tokens")},
        }
        headers = {"Content-Type": "application/json"}
    request = Request(f"{base_url}{endpoint}", data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    with LOCAL_OPENER.open(request, timeout=int(provider.get("timeout_seconds", 30))) as response:
        return _extract_response(name, json.loads(response.read().decode("utf-8")))


def ask_task(text: str, *, decision: dict[str, Any] | None = None, config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_router_config()
    decision = decision or route_task(text, config=config)
    if decision.get("status") != "LOCAL_MODEL_SELECTED":
        return {**decision, "response": decision.get("status", FALLBACK_STATUS)}
    candidates = list(decision.get("candidates", [])) or [
        {"provider": decision["provider"], "model": decision["model"], "base_url": decision["base_url"]}
    ]
    errors: list[str] = []
    for candidate in candidates:
        try:
            content = _ask_candidate(text, candidate, decision.get("parameters", {}), config)
            result = {**decision, **candidate, "status": "LOCAL_MODEL_RESPONSE", "response": content or "LOCAL_MODEL_EMPTY_RESPONSE"}
            append_route_log(result)
            return result
        except (HTTPError, URLError, OSError, TimeoutError, json.JSONDecodeError, ValueError, KeyError, TypeError) as exc:
            errors.append(f"{candidate.get('provider')}: {exc}")
    result = {**decision, "status": "LOCAL_MODEL_REQUEST_FAILED", "response": "NO_LOCAL_MODEL_ONLINE", "detail": "; ".join(errors)}
    append_route_log(result)
    return result


def router_status(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or load_router_config()
    states = probe_providers(config)
    available = {name: state.get("models", []) for name, state in states.items() if state.get("online")}
    last = None
    try:
        entries = json.loads(LOG_PATH.read_text(encoding="utf-8"))
        last = entries[-1] if entries else None
    except (OSError, json.JSONDecodeError):
        pass
    return {"local_only": config.get("local_only"), "cloud_enabled": config.get("cloud_enabled"), "providers": states, "default_provider": config.get("default_provider"), "available_models": available, "last_route_decision": last}


def print_status() -> dict[str, Any]:
    status = router_status()
    print(f"local_only: {str(status['local_only']).lower()}")
    print(f"cloud_enabled: {str(status['cloud_enabled']).lower()}")
    print(f"LM Studio: {'online' if status['providers'].get('lm_studio', {}).get('online') else 'offline'}")
    print(f"Ollama: {'online' if status['providers'].get('ollama', {}).get('online') else 'offline'}")
    print(f"selected default provider: {status['default_provider']}")
    print(f"available models: {json.dumps(status['available_models'])}")
    print(f"last route decision: {json.dumps(status['last_route_decision'])}")
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description="Hermes offline local model router")
    sub = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "providers", "models", "test"):
        sub.add_parser(command)
    for command in ("route", "ask"):
        child = sub.add_parser(command)
        child.add_argument("text")
    args = parser.parse_args()
    if args.command == "status":
        print_status()
    elif args.command == "providers":
        print(json.dumps(probe_providers(), indent=2))
    elif args.command == "models":
        states = probe_providers()
        print(json.dumps({name: state["models"] for name, state in states.items() if state["online"]}, indent=2))
    elif args.command == "route":
        print(json.dumps(route_task(args.text), indent=2))
    elif args.command == "ask":
        print(json.dumps(ask_task(args.text), indent=2))
    else:
        config = load_router_config()
        assert config["local_only"] is True and config["cloud_enabled"] is False
        offline = {name: {"online": False, "models": [], "base_url": None} for name in config["providers"]}
        assert route_task("test", states=offline, config=config)["status"] == FALLBACK_STATUS
        print("MODEL ROUTER TEST OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
