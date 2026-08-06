"""Deterministic, provider-neutral routing policy for Hermes.

The legacy router remains the execution adapter.  This module owns the policy
decisions so model capability and health rules do not leak into providers.
"""
from __future__ import annotations

import json
import logging
import random
import time
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable

LOG = logging.getLogger("hermes.router")


class RoutingMode(StrEnum):
    AUTO = "auto"
    HYBRID = "hybrid"
    MANUAL = "manual"


class HealthState(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    COOLING_DOWN = "cooling_down"
    UNAVAILABLE = "unavailable"
    DISABLED = "disabled"


TASK_PROFILES = (
    "general_chat", "fast_chat", "deep_reasoning", "coding", "vision",
    "creative_work", "structured_json", "long_context", "private_local",
)


@dataclass(frozen=True)
class ModelCapability:
    provider: str
    model_id: str
    local: bool = False
    context_window: int = 4096
    vision: bool = False
    tool_calling: bool = False
    structured_output: bool = False
    coding: bool = False
    reasoning: bool = False
    streaming: bool = False
    estimated_cost: float = 0.0
    privacy: str = "remote"
    enabled: bool = True
    latency_ms: int = 1000
    preference: float = 0.0

    @classmethod
    def from_config(cls, provider: str, model_id: str, value: dict[str, Any]) -> "ModelCapability":
        return cls(provider=provider, model_id=model_id, local=bool(value.get("local", False)),
                   context_window=int(value.get("context_window", value.get("context_tokens", 4096))),
                   vision=bool(value.get("vision", value.get("vision_support", False))),
                   tool_calling=bool(value.get("tool_calling", value.get("tools", False))),
                   structured_output=bool(value.get("structured_output", False)),
                   coding=bool(value.get("coding", False)), reasoning=bool(value.get("reasoning", False)),
                   streaming=bool(value.get("streaming", False)), estimated_cost=float(value.get("estimated_cost", value.get("cost", 0) or 0)),
                   privacy=str(value.get("privacy", "local" if value.get("local") else "remote")),
                   enabled=bool(value.get("enabled", True)), latency_ms=int(value.get("latency_ms", 1000)),
                   preference=float(value.get("preference", 0.0)))


@dataclass
class HealthRecord:
    state: HealthState = HealthState.HEALTHY
    failures: int = 0
    cooldown_until: float = 0.0
    rolling_latency_ms: float = 0.0
    successes: int = 0
    last_success: float | None = None
    last_failure_reason: str | None = None

    def available(self, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        return self.state not in {HealthState.DISABLED, HealthState.UNAVAILABLE} and self.cooldown_until <= now


@dataclass(frozen=True)
class RouteRequest:
    task_profile: str = "general_chat"
    privacy: str = "remote"
    required_capabilities: frozenset[str] = frozenset()
    context_tokens: int = 0
    preferred_provider: str | None = None
    preferred_model: str | None = None
    local_only: bool = False
    emergency_fallback: bool = False


class RouterPolicy:
    """Configurable deterministic selector with hard privacy/capability filters."""

    def __init__(self, config: dict[str, Any] | None = None, health: dict[tuple[str, str], HealthRecord] | None = None) -> None:
        self.config = config or {}
        self.mode = RoutingMode(str(self.config.get("mode", self.config.get("default_mode", "hybrid"))).lower())
        self.max_retries = max(0, int(self.config.get("max_retries", 1)))
        self.cooldown_seconds = max(1, int(self.config.get("cooldown_seconds", 300)))
        self.health = health if health is not None else {}

    @staticmethod
    def detect_task(text: str, *, has_attachments: bool = False, response_format: str | None = None) -> str:
        value = text.lower()
        if has_attachments or any(x in value for x in ("image", "screenshot", "photo", "vision", "pdf")):
            return "vision"
        if response_format == "json" or "json" in value or "structured output" in value:
            return "structured_json"
        if any(x in value for x in ("private", "do not send", "offline", "local only")):
            return "private_local"
        if any(x in value for x in ("implement", "code", "debug", "traceback", "patch", "function", "test")):
            return "coding"
        if any(x in value for x in ("reason deeply", "deep reasoning", "architecture", "prove", "analyze")):
            return "deep_reasoning"
        if any(x in value for x in ("creative", "story", "brainstorm", "write a poem")):
            return "creative_work"
        if len(value) > 12000 or "long context" in value:
            return "long_context"
        if len(value) < 160 or any(x in value for x in ("quick", "fast", "brief")):
            return "fast_chat"
        return "general_chat"

    def _hard_match(self, model: ModelCapability, request: RouteRequest) -> bool:
        if not model.enabled or not self.health.get((model.provider, model.model_id), HealthRecord()).available():
            return False
        if request.local_only or request.privacy == "local" or request.task_profile == "private_local":
            if not model.local or model.privacy not in {"local", "private"}:
                return False
        if request.context_tokens and model.context_window < request.context_tokens:
            return False
        for capability in request.required_capabilities:
            if not bool(getattr(model, capability, False)):
                return False
        if request.preferred_provider and model.provider != request.preferred_provider:
            return False
        return True

    def select(self, models: Iterable[ModelCapability], request: RouteRequest) -> list[tuple[ModelCapability, str]]:
        candidates = [m for m in models if self._hard_match(m, request)]
        preferred = [m for m in candidates if request.preferred_model and m.model_id == request.preferred_model]
        if self.mode == RoutingMode.MANUAL and not request.emergency_fallback:
            return [(m, "manual selection") for m in preferred[:1]]
        if self.mode == RoutingMode.HYBRID:
            candidates = preferred + [m for m in candidates if m not in preferred]

        def score(model: ModelCapability) -> float:
            health = self.health.get((model.provider, model.model_id), HealthRecord())
            success_rate = health.successes / max(health.successes + health.failures, 1)
            task_fit = float({
                "coding": model.coding,
                "deep_reasoning": model.reasoning,
                "vision": model.vision,
                "structured_json": model.structured_output,
            }.get(request.task_profile, True))
            return task_fit * 4 + success_rate * 2 + model.preference - model.estimated_cost - model.latency_ms / 100000

        if self.mode == RoutingMode.AUTO:
            candidates.sort(key=score, reverse=True)
        return [(m, "preferred model" if request.preferred_model == m.model_id else "deterministic policy score") for m in candidates]

    def record_success(self, model: ModelCapability, latency_ms: int) -> None:
        health = self.health.setdefault((model.provider, model.model_id), HealthRecord())
        health.state, health.successes, health.last_success = HealthState.HEALTHY, health.successes + 1, time.time()
        health.rolling_latency_ms = latency_ms if not health.rolling_latency_ms else (health.rolling_latency_ms * .8 + latency_ms * .2)

    def record_failure(self, model: ModelCapability, reason: str, *, now: float | None = None) -> None:
        health = self.health.setdefault((model.provider, model.model_id), HealthRecord())
        health.failures += 1
        health.last_failure_reason = reason
        health.cooldown_until = (time.time() if now is None else now) + self.cooldown_seconds
        health.state = HealthState.COOLING_DOWN if health.failures < 3 else HealthState.UNAVAILABLE

    def retry_delay(self, attempt: int, *, rng: Any = random.random) -> float:
        base = min(30.0, 0.25 * (2 ** max(0, attempt)))
        return base + rng() * base * 0.25


def load_capabilities(path: str | Path) -> list[ModelCapability]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    models = data.get("models", data) if isinstance(data, dict) else data
    result: list[ModelCapability] = []
    for item in models if isinstance(models, list) else []:
        if isinstance(item, dict) and item.get("provider") and item.get("model_id"):
            result.append(ModelCapability.from_config(str(item["provider"]), str(item["model_id"]), item))
    return result
