from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from backend.services.provider_registry import DEFAULT_CONFIG_PATH, load_rotation_config


CLOUD_UNLOCK_PHRASE = "UNLOCK CLOUD FOR THIS ONE TASK"


@dataclass
class AccessDecision:
    allowed: bool
    reason: str


class CreditGuard:
    def __init__(
        self,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        hermes_dir: str | Path | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.config = load_rotation_config(self.config_path)
        self.project_root = self.config_path.resolve().parents[1]
        self.hermes_dir = Path(hermes_dir) if hermes_dir else self.project_root / ".hermes"
        self.log_path = self.hermes_dir / "logs" / "credit_guard.log"
        self.state_path = self.hermes_dir / "cloud_unlock.json"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.state_path.exists():
            self._write_state({"unlocked": False, "remaining_tasks": 0})

    def _read_state(self) -> dict[str, Any]:
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return {"unlocked": False, "remaining_tasks": 0}

    def _write_state(self, state: dict[str, Any]) -> None:
        self.state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _is_cloud_provider(self, provider_name: str, provider: dict[str, Any]) -> bool:
        base_url = str(provider.get("base_url", "")).lower()
        if provider_name in {"openai", "openrouter_locked", "anthropic"}:
            return True
        if base_url.startswith("https://"):
            return True
        return not any(token in base_url for token in ("localhost", "127.0.0.1")) and provider.get("type") != "mlx_local"

    def _log_block(self, provider_name: str, reason: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{provider_name}: {reason}\n")

    def unlock_for_task(self, phrase: str) -> bool:
        if phrase != CLOUD_UNLOCK_PHRASE:
            return False
        self._write_state({"unlocked": True, "remaining_tasks": 1})
        return True

    def complete_task(self) -> None:
        state = self._read_state()
        if state.get("remaining_tasks", 0) > 0:
            state["remaining_tasks"] = 0
            state["unlocked"] = False
            self._write_state(state)

    def can_use_provider(self, provider_name: str, provider: dict[str, Any]) -> AccessDecision:
        if not self._is_cloud_provider(provider_name, provider):
            return AccessDecision(True, "local provider allowed")

        safety = self.config.get("safety", {})
        cost = provider.get("cost")
        state = self._read_state()
        unlocked = bool(state.get("unlocked")) and int(state.get("remaining_tasks", 0)) > 0

        if cost == "paid" and not unlocked:
            reason = "paid provider blocked by default"
            self._log_block(provider_name, reason)
            return AccessDecision(False, reason)

        blocked_names = {
            "openai": not safety.get("allow_openai", False),
            "openrouter_locked": not safety.get("allow_openrouter", False),
            "anthropic": not safety.get("allow_anthropic", False),
        }
        if blocked_names.get(provider_name, False) and not unlocked:
            reason = f"{provider_name} blocked by default safety policy"
            self._log_block(provider_name, reason)
            return AccessDecision(False, reason)

        if cost in {None, "", "unknown"} and safety.get("stop_if_provider_cost_unknown", True):
            reason = "provider cost unknown; blocking cloud call"
            self._log_block(provider_name, reason)
            return AccessDecision(False, reason)

        if not unlocked:
            reason = "cloud provider requires exact manual unlock phrase"
            self._log_block(provider_name, reason)
            return AccessDecision(False, reason)

        if cost == "paid" and not self.config.get("cloud_unlock", {}).get("paid_models_allowed", False):
            reason = "paid cloud models remain blocked even when cloud unlock is active"
            self._log_block(provider_name, reason)
            return AccessDecision(False, reason)

        return AccessDecision(True, "manual cloud unlock active for one task")
