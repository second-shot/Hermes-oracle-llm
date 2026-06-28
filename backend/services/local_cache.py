from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.services.provider_registry import DEFAULT_CONFIG_PATH, load_rotation_config


class LocalCache:
    def __init__(
        self,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        hermes_dir: str | Path | None = None,
    ) -> None:
        self.config = load_rotation_config(config_path)
        project_root = Path(config_path).resolve().parents[1]
        self.hermes_dir = Path(hermes_dir) if hermes_dir else project_root / ".hermes"
        self.cache_dir = self.hermes_dir / "cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.exact_path = self.cache_dir / "exact.json"
        self.semantic_path = self.cache_dir / "semantic.json"
        self.tool_path = self.cache_dir / "tool_outputs.json"
        for path in (self.exact_path, self.semantic_path, self.tool_path):
            if not path.exists():
                path.write_text("{}", encoding="utf-8")

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def make_key(self, payload: Any) -> str:
        raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _signature(self, payload: Any) -> str:
        if isinstance(payload, str):
            return payload.lower()
        if isinstance(payload, dict):
            return json.dumps(payload, sort_keys=True, ensure_ascii=False).lower()
        return str(payload).lower()

    def _similarity(self, left: str, right: str) -> float:
        left_tokens = set(left.split())
        right_tokens = set(right.split())
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)

    def get_exact(self, key: str) -> Any | None:
        return self._read_json(self.exact_path).get(key, {}).get("response")

    def set_model_output(self, key: str, response: Any, payload: Any | None = None) -> None:
        exact = self._read_json(self.exact_path)
        exact[key] = {"response": response, "saved_at": datetime.utcnow().isoformat()}
        self._write_json(self.exact_path, exact)

        if payload is not None:
            semantic = self._read_json(self.semantic_path)
            semantic[key] = {
                "signature": self._signature(payload),
                "response": response,
                "saved_at": datetime.utcnow().isoformat(),
            }
            self._write_json(self.semantic_path, semantic)

    def set_tool_output(self, tool_name: str, payload: Any, response: Any) -> None:
        data = self._read_json(self.tool_path)
        cache_key = self.make_key({"tool": tool_name, "payload": payload})
        data[cache_key] = {
            "tool": tool_name,
            "response": response,
            "signature": self._signature(payload),
            "saved_at": datetime.utcnow().isoformat(),
        }
        self._write_json(self.tool_path, data)

    def get_cached_response(self, key: str, payload: Any) -> Any | None:
        exact = self.get_exact(key)
        if exact is not None:
            return exact

        semantic = self._read_json(self.semantic_path)
        target = self._signature(payload)
        threshold = float(self.config.get("cache", {}).get("semantic_threshold", 0.88))
        best_response = None
        best_score = 0.0
        for item in semantic.values():
            score = self._similarity(target, str(item.get("signature", "")))
            if score > best_score:
                best_score = score
                best_response = item.get("response")
        if best_score >= threshold:
            return best_response
        return None
