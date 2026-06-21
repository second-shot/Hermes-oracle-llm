from __future__ import annotations

import argparse
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .responses import error
from .service import OracleService


class OracleApiServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], handler_class: type[BaseHTTPRequestHandler], service: OracleService):
        super().__init__(server_address, handler_class)
        self.service = service


class OracleApiHandler(BaseHTTPRequestHandler):
    server: OracleApiServer

    def do_OPTIONS(self) -> None:
        self._send_json(200, {"status": "ok", "data": {}, "meta": {}})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        routes = {
            "/api/health": self.server.service.health,
            "/api/oracle/state": self.server.service.get_state,
            "/api/oracle/events": self.server.service.list_events,
            "/api/confirmations": self.server.service.list_confirmations,
            "/api/notifications": self.server.service.list_notifications,
            "/api/memory": self.server.service.get_memory,
            "/api/logs": self.server.service.get_logs,
        }
        handler = routes.get(path)
        if handler is None:
            self._send_json(404, error("not_found", f"Path '{path}' is not available."))
            return
        self._send_json(200, handler())

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        payload = self._read_json_body()
        if path == "/api/oracle/intake":
            self._send_json(200, self.server.service.submit_intake(payload))
            return
        if path == "/api/tasks/execute":
            self._send_json(200, self.server.service.request_task_execution(payload))
            return
        approve_match = re.fullmatch(r"/api/confirmations/([^/]+)/approve", path)
        if approve_match:
            self._send_json(200, self.server.service.approve_confirmation(approve_match.group(1), payload))
            return
        reject_match = re.fullmatch(r"/api/confirmations/([^/]+)/reject", path)
        if reject_match:
            self._send_json(200, self.server.service.reject_confirmation(reject_match.group(1), payload))
            return
        self._send_json(404, error("not_found", f"Path '{path}' is not available."))

    def _read_json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length == 0:
            return {}
        body = self.rfile.read(length).decode("utf-8")
        return json.loads(body)

    def _send_json(self, status_code: int, payload: dict) -> None:
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args) -> None:
        return None


def build_server(host: str, port: int, data_root: Path | None = None) -> OracleApiServer:
    root = Path(data_root) if data_root is not None else Path(__file__).resolve().parent.parent
    service = OracleService(root)
    return OracleApiServer((host, port), OracleApiHandler, service)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Oracle V1 local HTTP API")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--data-root", default=str(Path(__file__).resolve().parent.parent))
    args = parser.parse_args(argv)

    server = build_server(args.host, args.port, Path(args.data_root))
    print(f"Oracle V1 API listening on http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
