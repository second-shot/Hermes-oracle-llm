from __future__ import annotations

import json
import time
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from backend.services.model_router import ModelRouter
from backend.services.provider_registry import DEFAULT_CONFIG_PATH, load_rotation_config
from core.executor import execute_task


REPO_ROOT = Path(__file__).resolve().parents[2]
_EXECUTOR_LOCK = threading.Lock()


def load_config() -> dict[str, Any]:
    with (REPO_ROOT / "config.json").open("r", encoding="utf-8") as handle:
        return json.load(handle)


def list_models() -> dict[str, Any]:
    rotation = load_rotation_config(DEFAULT_CONFIG_PATH)
    models = []
    for model_key, model in rotation.get("models", {}).items():
        candidates = model.get("model_candidates", [])
        models.append(
            {
                "id": candidates[0] if candidates else model_key,
                "object": "model",
                "owned_by": "hermes",
                "metadata": {
                    "model_key": model_key,
                    "role": model.get("role", ""),
                    "provider_order": model.get("provider_order", []),
                },
            }
        )
    return {"object": "list", "data": models}


def _completion_payload(payload: dict[str, Any], text: str) -> dict[str, Any]:
    return {
        "id": f"chatcmpl-hermes-{int(time.time())}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": str(payload.get("model", "hermes-local")),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


def provider_health() -> dict[str, Any]:
    router = ModelRouter()
    return router.provider_health(load_config())


def chat_completion(payload: dict[str, Any]) -> dict[str, Any]:
    messages = payload.get("messages", [])
    user_text = ""
    if isinstance(messages, list):
        for message in reversed(messages):
            if isinstance(message, dict) and message.get("role") == "user":
                user_text = str(message.get("content", "")).strip()
                break

    # Only one local inference may run at a time. Starting overlapping requests
    # can make LM Studio load or unload models concurrently and destabilize the
    # desktop process, especially while the selected model is changing.
    if not _EXECUTOR_LOCK.acquire(blocking=False):
        return _completion_payload(
            payload,
            "Hermes is already processing a local model request. Let the active request finish before changing models or sending another prompt.",
        )

    result_holder: dict[str, Any] = {}

    def _run_executor() -> None:
        try:
            result_holder["value"] = execute_task(user_text or "help", load_config())
        except Exception as exc:  # pragma: no cover - defensive fallback
            result_holder["error"] = exc
        finally:
            _EXECUTOR_LOCK.release()

    worker = threading.Thread(target=_run_executor, daemon=True)
    try:
        worker.start()
    except Exception:
        _EXECUTOR_LOCK.release()
        raise
    worker.join(timeout=5)

    text = "Hermes is warming up locally and returned a safe stub response."
    result = result_holder.get("value")
    if worker.is_alive():
        text = "Hermes is still warming up locally. The active request is continuing; do not start another request or change models until it finishes."
    elif isinstance(result, dict):
        text = str(result.get("result") or result.get("message") or text)
    elif result_holder.get("error") is not None:
        text = f"Hermes local execution failed: {result_holder['error']}"
    if isinstance(result, dict) and result.get("fallback_notice"):
        notice = str(result["fallback_notice"]).strip()
        if notice and not text.startswith(notice):
            text = f"{notice}\n\n{text}"

    response = _completion_payload(payload, text)
    if isinstance(result, dict):
        response["meta"] = {
            "provider": result.get("meta", {}).get("provider"),
            "model": result.get("meta", {}).get("model"),
            "execution_scope": result.get("meta", {}).get("mode"),
            "fallback_notice": result.get("fallback_notice"),
            "fallback_reason": result.get("fallback_notice"),
        }
        if result.get("fallback_notice"):
            response["fallback_notice"] = result["fallback_notice"]
    return response


class HermesAPIHandler(BaseHTTPRequestHandler):
    server_version = "HermesAPI/1.0"

    def _send_json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        if self.path in {"/", "/health", "/v1/health"}:
            self._send_json(200, {"status": "ok", "service": "hermes", "provider_health": provider_health()})
            return
        if self.path == "/api/status":
            self._send_json(200, {"status": "ok", "service": "hermes", "provider_health": provider_health()})
            return
        if self.path == "/v1/models":
            self._send_json(200, list_models())
            return
        self._send_json(404, {"error": {"message": "Not found"}})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/v1/chat/completions":
            self._send_json(404, {"error": {"message": "Not found"}})
            return
        try:
            payload = self._read_json()
        except json.JSONDecodeError:
            self._send_json(400, {"error": {"message": "Invalid JSON"}})
            return
        if not isinstance(payload, dict):
            self._send_json(400, {"error": {"message": "Request body must be an object"}})
            return
        self._send_json(200, chat_completion(payload))

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        return


def run_server(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), HermesAPIHandler)
    print(f"Hermes API listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
