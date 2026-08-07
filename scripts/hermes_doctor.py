from __future__ import annotations

import argparse
import importlib
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.routes.llm import run_server
from backend.services.provider_registry import DEFAULT_CONFIG_PATH, load_rotation_config


def _ok(message: str) -> None:
    print(f"[OK]   {message}")


def _warn(message: str) -> None:
    print(f"[WARN] {message}")


def _fail(message: str) -> None:
    print(f"[FAIL] {message}")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _headers_for(provider: dict[str, Any]) -> dict[str, str]:
    headers = {"Accept": "application/json"}
    env_key = str(provider.get("env_key", "")).strip()
    token = os.environ.get(env_key, "").strip() if env_key else ""
    if not token and env_key == "LM_STUDIO_API_TOKEN":
        token = os.environ.get("LM_API_TOKEN", "").strip()
    api_key = str(provider.get("api_key", "")).strip()
    if not token and api_key.lower() not in {"", "local", "lm-studio", "placeholder", "changeme", "none"}:
        token = api_key
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _get_json(url: str, headers: dict[str, str] | None = None, timeout: float = 2.0) -> dict[str, Any]:
    request = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{url} did not return a JSON object")
    return payload


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        return sock.connect_ex((host, port)) == 0


def check_python() -> bool:
    if sys.version_info < (3, 10):
        _fail(f"Python 3.10+ required; found {sys.version.split()[0]}")
        return False
    _ok(f"Python {sys.version.split()[0]}")
    return True


def check_dependencies() -> bool:
    required = ("fastapi", "dotenv", "openai")
    missing: list[str] = []
    for module_name in required:
        try:
            importlib.import_module(module_name)
        except Exception:
            missing.append(module_name)
    if missing:
        _fail("Missing Python packages: " + ", ".join(missing))
        print("       Run: python -m pip install -r requirements.txt")
        return False
    _ok("Python dependencies")
    return True


def check_local_only_config() -> tuple[bool, dict[str, Any], dict[str, Any]]:
    config_path = REPO_ROOT / "config.json"
    try:
        config = _load_json(config_path)
        rotation = load_rotation_config(DEFAULT_CONFIG_PATH)
    except Exception as exc:
        _fail(f"Configuration could not be loaded: {exc}")
        return False, {}, {}

    problems: list[str] = []
    if config.get("cloud_enabled") is not False:
        problems.append("config.json cloud_enabled must be false")
    if str(config.get("llm", {}).get("provider", "")).lower() != "local_router":
        problems.append("config.json llm.provider must be local_router")
    safety = rotation.get("safety", {})
    hermes = rotation.get("hermes", {})
    if safety.get("allow_openai") is not False:
        problems.append("rotation safety.allow_openai must be false")
    if hermes.get("cloud_auto_fallback") is not False:
        problems.append("rotation hermes.cloud_auto_fallback must be false")

    if problems:
        for problem in problems:
            _fail(problem)
        return False, config, rotation

    _ok("Local-only provider configuration")
    return True, config, rotation


def resolve_runtime(rotation: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    runtime_name = str(rotation.get("hermes", {}).get("default_runtime", "lmstudio_windows"))
    providers = rotation.get("providers", {})
    provider = providers.get(runtime_name, {})
    if not isinstance(provider, dict):
        provider = {}
    return runtime_name, provider


def check_lm_studio(rotation: dict[str, Any]) -> bool:
    runtime_name, provider = resolve_runtime(rotation)
    base_url = str(provider.get("base_url", "http://127.0.0.1:1234/v1")).rstrip("/")
    headers = _headers_for(provider)
    try:
        models = _get_json(f"{base_url}/models", headers=headers, timeout=2.0)
    except urllib.error.HTTPError as exc:
        if exc.code in {401, 403}:
            env_key = str(provider.get("env_key", "LM_STUDIO_API_TOKEN"))
            _fail(f"{runtime_name} rejected authentication at {base_url}")
            print(f"       Set {env_key} to the token configured in LM Studio, then retry.")
        else:
            _fail(f"{runtime_name} returned HTTP {exc.code} at {base_url}")
        return False
    except Exception:
        _fail(f"LM Studio is not reachable at {base_url}")
        print("       Open LM Studio, load one model, and start the Local Server.")
        return False

    available = [
        str(item.get("id"))
        for item in models.get("data", [])
        if isinstance(item, dict) and item.get("id")
    ]
    if not available:
        _fail("LM Studio is running but no model is loaded")
        print("       Run scripts\\start_local_model.cmd, then retry.")
        return False

    expected = str(provider.get("model", "")).strip()
    if expected and expected not in available:
        _fail(f"Expected LM Studio model {expected!r}, but loaded: {', '.join(available)}")
        print("       Run scripts\\start_local_model.cmd to load the correct free model.")
        return False

    _ok(f"LM Studio model: {expected or available[0]}")
    return True


def check_ollama(rotation: dict[str, Any]) -> bool:
    runtime_name, provider = resolve_runtime(rotation)
    base_url = str(provider.get("base_url", "http://127.0.0.1:11434")).rstrip("/")
    health_path = str(provider.get("health_path", "/api/tags"))
    try:
        tags = _get_json(
            f"{base_url}{health_path}",
            timeout=float(provider.get("model_discovery_timeout_seconds", 2)),
        )
    except Exception:
        _fail(f"Ollama is not reachable at {base_url}")
        print("       Start Ollama, then retry Hermes.")
        return False

    available = [
        str(item.get("name") or item.get("model"))
        for item in tags.get("models", [])
        if isinstance(item, dict) and (item.get("name") or item.get("model"))
    ]
    if not available:
        _fail("Ollama is running but no models are installed")
        print("       Run: ollama pull llama3.2:3b")
        return False

    expected = str(provider.get("model", "llama3.2:3b")).strip()
    if expected and expected not in available:
        _fail(f"Expected Ollama model {expected!r}, but installed: {', '.join(available)}")
        print("       Run: ollama pull " + expected)
        return False

    _ok(f"Ollama model: {expected or available[0]}")
    return True


def check_existing_hermes(host: str, port: int) -> bool:
    url = f"http://{host}:{port}/v1/health"
    try:
        health = _get_json(url, timeout=1.0)
    except Exception:
        return False
    if health.get("status") == "ok" and health.get("service") == "hermes":
        _ok(f"Hermes API already running at http://{host}:{port}")
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose and start Hermes safely on Windows.")
    parser.add_argument("--start", action="store_true", help="Start the Hermes API after checks pass.")
    parser.add_argument("--allow-stub", action="store_true", help="Allow startup without an active LM Studio model.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    os.chdir(REPO_ROOT)
    print(f"Hermes Doctor | repo={REPO_ROOT}")

    checks_ok = check_python()
    checks_ok = check_dependencies() and checks_ok
    config_ok, _config, rotation = check_local_only_config()
    checks_ok = config_ok and checks_ok

    already_running = check_existing_hermes(args.host, args.port)
    if already_running:
        return 0

    if _port_open(args.host, args.port):
        _fail(f"Port {args.port} is occupied by a non-Hermes process")
        print(f"       Run: netstat -ano | findstr :{args.port}")
        return 1

    runtime_name = str(rotation.get("hermes", {}).get("default_runtime", "lmstudio_windows")) if rotation else ""
    runtime_ok = check_ollama(rotation) if runtime_name == "ollama" else (check_lm_studio(rotation) if rotation else False)
    if not runtime_ok and not args.allow_stub:
        checks_ok = False
    elif not runtime_ok:
        _warn("Starting in deterministic stub mode because --allow-stub was supplied")

    if not checks_ok:
        print("\nHermes is not ready. Correct the failed checks and run start-hermes.cmd again.")
        return 1

    if not args.start:
        print("\nHermes is ready. Run: start-hermes.cmd")
        return 0

    print(f"\nStarting Hermes API at http://{args.host}:{args.port}")
    print("Keep this window open. Press Ctrl+C to stop Hermes.")
    try:
        run_server(host=args.host, port=args.port)
    except OSError as exc:
        _fail(f"Hermes API could not bind to {args.host}:{args.port}: {exc}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
