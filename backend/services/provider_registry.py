from __future__ import annotations

import json
import socket
import sys
import urllib.error
import urllib.request
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "hermes.model.rotation.yaml"


def _strip_comments(text: str) -> list[str]:
    return [line.rstrip("\n") for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if not value:
        return ""
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered == "null":
        return None
    if lowered == "paid":
        return "paid"
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value


def _parse_block(lines: list[str], start: int, indent: int) -> tuple[Any, int]:
    result: Any = None
    index = start
    while index < len(lines):
        raw = lines[index]
        current_indent = len(raw) - len(raw.lstrip(" "))
        if current_indent < indent:
            break
        if current_indent > indent:
            raise ValueError(f"Unexpected indentation in YAML near: {raw}")

        content = raw.strip()
        if content.startswith("- "):
            if result is None:
                result = []
            item_text = content[2:].strip()
            index += 1
            if not item_text:
                item, index = _parse_block(lines, index, indent + 2)
                result.append(item)
                continue
            if ":" in item_text:
                key, rest = item_text.split(":", 1)
                item: dict[str, Any] = {}
                rest = rest.strip()
                if rest:
                    item[key.strip()] = _parse_scalar(rest)
                else:
                    nested, index = _parse_block(lines, index, indent + 2)
                    item[key.strip()] = nested
                if index < len(lines):
                    next_indent = len(lines[index]) - len(lines[index].lstrip(" "))
                    if next_indent == indent + 2 and not lines[index].strip().startswith("- "):
                        nested, index = _parse_block(lines, index, indent + 2)
                        if isinstance(nested, dict):
                            item.update(nested)
                result.append(item)
                continue
            result.append(_parse_scalar(item_text))
            continue

        if result is None:
            result = {}
        key, rest = content.split(":", 1)
        rest = rest.strip()
        index += 1
        if rest:
            result[key.strip()] = _parse_scalar(rest)
            continue
        nested, index = _parse_block(lines, index, indent + 2)
        result[key.strip()] = nested

    return result if result is not None else {}, index


def load_rotation_config(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    path = Path(config_path)
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(text)
        if isinstance(data, dict):
            return data
    except Exception:
        pass

    parsed, _ = _parse_block(_strip_comments(text), 0, 0)
    if not isinstance(parsed, dict):
        raise ValueError(f"Rotation config at {path} must contain a mapping root")
    return parsed


def sanitize_provider(provider_name: str, provider: dict[str, Any]) -> dict[str, Any]:
    clean = deepcopy(provider)
    if "api_key" in clean:
        clean["api_key"] = "<redacted>"
    if "env_key" in clean:
        clean["env_key"] = "<redacted>"
    clean["name"] = provider_name
    return clean


@dataclass
class ProviderStatus:
    name: str
    provider: dict[str, Any]
    available: bool
    is_cloud: bool
    priority: int
    routing_score: float


class ProviderRegistry:
    def __init__(
        self,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        hermes_dir: str | Path | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.config = load_rotation_config(self.config_path)
        self.project_root = self.config_path.resolve().parents[1]
        self.hermes_dir = Path(hermes_dir) if hermes_dir else self.project_root / ".hermes"
        self.hermes_dir.mkdir(parents=True, exist_ok=True)

    def providers(self) -> dict[str, dict[str, Any]]:
        return self.config.get("providers", {})

    def models(self) -> dict[str, dict[str, Any]]:
        return self.config.get("models", {})

    def is_cloud_provider(self, provider: dict[str, Any]) -> bool:
        base_url = str(provider.get("base_url", "")).lower()
        if base_url.startswith("https://"):
            return True
        if base_url.startswith("http://localhost") or base_url.startswith("http://127.0.0.1"):
            return False
        provider_type = str(provider.get("type", "")).lower()
        return provider_type not in {"mlx_local"} and "local" not in provider_type

    def _probe_http(self, base_url: str) -> bool:
        targets = [base_url.rstrip("/"), base_url.rstrip("/") + "/models"]
        for target in targets:
            try:
                request = urllib.request.Request(target, method="GET")
                with urllib.request.urlopen(request, timeout=0.35) as response:
                    if 200 <= getattr(response, "status", 200) < 500:
                        return True
            except urllib.error.HTTPError as exc:
                if exc.code < 500:
                    return True
            except Exception:
                continue
        return False

    def _probe_provider(self, provider_name: str, provider: dict[str, Any]) -> bool:
        if not provider.get("enabled", False):
            return False
        if provider_name == "mlx_mac":
            return sys.platform == "darwin" and "arm" in getattr(__import__("platform"), "machine")().lower()

        base_url = str(provider.get("base_url", ""))
        if not base_url:
            return False
        if "localhost" not in base_url and "127.0.0.1" not in base_url:
            return True
        return self._probe_http(base_url)

    def _score_provider(self, provider_name: str, provider: dict[str, Any], task_route: str, model_key: str) -> float:
        weights = self.config.get("routing", {}).get("scoring_formula", {})
        model_config = self.models().get(model_key, {})
        provider_order = model_config.get("provider_order", [])
        capability = 1.0 if provider_name in provider_order else 0.4
        task_match = 1.0 if provider_name in provider_order[:2] else 0.5
        speed = 1.0 / max(int(provider.get("priority", 1)), 1)
        memory_fit = min(float(model_config.get("params", {}).get("context_tokens", 4096)) / 8192.0, 1.0)
        recent_success = 0.8
        context_fit = 1.0 if task_route in {"repo_debug", "code_patch"} and provider_name != "mlx_mac" else 0.7
        failure_penalty = 0.0
        cost_penalty = 0.0 if provider.get("cost", 0) in {0, "0", "free"} else float(weights.get("cost_penalty_weight", 9999))
        return (
            float(weights.get("capability_weight", 0.38)) * capability
            + float(weights.get("task_match_weight", 0.24)) * task_match
            + float(weights.get("speed_weight", 0.12)) * speed
            + float(weights.get("memory_fit_weight", 0.10)) * memory_fit
            + float(weights.get("recent_success_weight", 0.08)) * recent_success
            + float(weights.get("context_fit_weight", 0.05)) * context_fit
            - float(weights.get("failure_penalty_weight", 0.20)) * failure_penalty
            - cost_penalty
        )

    def available_providers(
        self,
        task_route: str,
        model_key: str,
        credit_guard: Any | None = None,
    ) -> list[ProviderStatus]:
        statuses: list[ProviderStatus] = []
        for provider_name, provider in self.providers().items():
            if credit_guard is not None:
                decision = credit_guard.can_use_provider(provider_name, provider)
                if not decision.allowed:
                    continue
            try:
                available = self._probe_provider(provider_name, provider)
            except Exception:
                available = False
            if not available:
                continue
            statuses.append(
                ProviderStatus(
                    name=provider_name,
                    provider=sanitize_provider(provider_name, provider),
                    available=True,
                    is_cloud=self.is_cloud_provider(provider),
                    priority=int(provider.get("priority", 999)),
                    routing_score=self._score_provider(provider_name, provider, task_route, model_key),
                )
            )

        return sorted(statuses, key=lambda item: (item.priority, -item.routing_score, item.name))

    def save_snapshot(self) -> Path:
        snapshot_path = self.hermes_dir / "provider_registry.snapshot.json"
        data = {
            "providers": [status.__dict__ for status in self.available_providers("simple_chat", "fast_chat")],
        }
        snapshot_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return snapshot_path
