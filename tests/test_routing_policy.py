from __future__ import annotations

import time

from backend.services.routing_policy import (
    HealthState, ModelCapability, RouteRequest, RouterPolicy, RoutingMode,
)


def models():
    return [
        ModelCapability("cloud", "fast", context_window=4096, coding=True, estimated_cost=1, latency_ms=100),
        ModelCapability("ollama", "coder", local=True, context_window=8192, coding=True, structured_output=True, privacy="local"),
    ]


def test_hybrid_prefers_selected_model():
    policy = RouterPolicy({"mode": "hybrid"})
    result = policy.select(models(), RouteRequest(preferred_model="fast"))
    assert result[0][0].model_id == "fast"


def test_manual_does_not_fallback_without_emergency_toggle():
    policy = RouterPolicy({"mode": "manual"})
    result = policy.select(models(), RouteRequest(preferred_model="missing"))
    assert result == []


def test_local_only_is_a_hard_filter():
    policy = RouterPolicy({"mode": "auto"})
    result = policy.select(models(), RouteRequest(local_only=True))
    assert [item.model_id for item, _ in result] == ["coder"]


def test_capability_and_context_are_hard_filters():
    policy = RouterPolicy({"mode": "auto"})
    result = policy.select(models(), RouteRequest(required_capabilities=frozenset({"structured_output"}), context_tokens=6000))
    assert [item.model_id for item, _ in result] == ["coder"]


def test_circuit_breaker_cools_then_unavailable():
    policy = RouterPolicy({"mode": "auto", "cooldown_seconds": 60})
    model = models()[0]
    policy.record_failure(model, "http_429")
    assert policy.health[("cloud", "fast")].state == HealthState.COOLING_DOWN
    assert policy.select([model], RouteRequest()) == []
    policy.health[("cloud", "fast")].cooldown_until = 0
    policy.record_failure(model, "timeout", now=100)
    policy.health[("cloud", "fast")].cooldown_until = 0
    policy.record_failure(model, "timeout", now=100)
    assert policy.health[("cloud", "fast")].state == HealthState.UNAVAILABLE


def test_backoff_is_bounded_and_jittered():
    policy = RouterPolicy({"max_retries": 2})
    assert 0.25 <= policy.retry_delay(0, rng=lambda: 0) <= 30
    assert policy.retry_delay(10, rng=lambda: 0) <= 30
