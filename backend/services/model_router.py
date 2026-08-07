from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from backend.services.credit_guard import CLOUD_UNLOCK_PHRASE, CreditGuard
from backend.services.local_cache import LocalCache
from backend.services.provider_registry import DEFAULT_CONFIG_PATH, ProviderRegistry, load_rotation_config
from backend.services.repo_indexer import RepoIndexer
from backend.services.routing_policy import RouteRequest, RouterPolicy, RoutingMode, load_capabilities


class ModelRouter:
    CLOUD_FALLBACK_NOTICE = "Cloud credits exhausted. Switched to local offline model."
    CLOUD_FALLBACK_UNAVAILABLE_MESSAGE = (
        "Cloud credits exhausted and local Ollama is not available. Start Ollama or add credits."
    )

    def __init__(
        self,
        config_path: str | Path = DEFAULT_CONFIG_PATH,
        hermes_dir: str | Path | None = None,
        provider_registry: ProviderRegistry | None = None,
        credit_guard: CreditGuard | None = None,
        cache: LocalCache | None = None,
        repo_indexer: RepoIndexer | None = None,
        memory_reader: Callable[[dict[str, Any]], Any] | None = None,
    ) -> None:
        self.config_path = Path(config_path)
        self.config = load_rotation_config(self.config_path)
        self.project_root = self.config_path.resolve().parents[1]
        self.hermes_dir = Path(hermes_dir) if hermes_dir else self.project_root / ".hermes"
        self.provider_registry = provider_registry or ProviderRegistry(self.config_path, self.hermes_dir)
        self.credit_guard = credit_guard or CreditGuard(self.config_path, self.hermes_dir)
        self.cache = cache or LocalCache(self.config_path, self.hermes_dir)
        self.repo_indexer = repo_indexer or RepoIndexer(self.project_root, self.config_path, self.hermes_dir)
        self.memory_reader = memory_reader or (lambda _plan: {})
        policy_config = self.config.get("routing", {})
        self.policy = RouterPolicy(policy_config)
        capability_path = self.project_root / "config" / "model_capabilities.json"
        try:
            self.capabilities = load_capabilities(capability_path)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            self.capabilities = []
        self.audit_log_path = self.hermes_dir / "logs" / "model_router_audit.json"
        self.cooldown_state_path = self.hermes_dir / "provider_cooldowns.json"
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.cooldown_state_path.parent.mkdir(parents=True, exist_ok=True)

    def classify_task(self, user_input: str) -> str:
        text = user_input.lower()
        if any(token in text for token in ("screenshot", "image", "vision", "pdf", "ui")):
            return "screenshot_or_image"
        if any(token in text for token in ("summarise memory", "summarize memory", "archive memory", "compress memory")):
            return "summarise_memory"
        if any(token in text for token in ("patch", "implement", "edit", "update", "modify")):
            return "code_patch"
        if any(token in text for token in ("repo", "debug", "failing test", "bug", "traceback", "stack trace")):
            return "repo_debug"
        if any(token in text for token in ("architecture", "design", "plan", "system")):
            return "architecture_plan"
        return "simple_chat"

    def routing_mode(self, runtime_config: dict[str, Any] | None = None) -> str:
        runtime_config = runtime_config or {}
        value = runtime_config.get("routing_mode", self.config.get("routing", {}).get("mode", "hybrid"))
        try:
            return RoutingMode(str(value).lower()).value
        except ValueError:
            raise ValueError("routing mode must be one of: auto, hybrid, manual") from None

    def route_request(self, user_input: str, runtime_config: dict[str, Any] | None = None, **kwargs: Any) -> dict[str, Any]:
        """Return an explainable, side-effect-free routing decision."""
        runtime_config = runtime_config or {}
        mode = self.routing_mode(runtime_config)
        request = RouteRequest(
            task_profile=self.policy.detect_task(user_input, has_attachments=bool(kwargs.get("has_attachments")), response_format=kwargs.get("response_format")),
            privacy="local" if runtime_config.get("local_only") else "remote",
            required_capabilities=frozenset(kwargs.get("required_capabilities", ())),
            context_tokens=int(kwargs.get("context_tokens", 0)),
            preferred_provider=runtime_config.get("preferred_provider"),
            preferred_model=runtime_config.get("preferred_model") or runtime_config.get("llm", {}).get("model"),
            local_only=bool(runtime_config.get("local_only")),
            emergency_fallback=bool(runtime_config.get("emergency_fallback")),
        )
        self.policy.mode = RoutingMode(mode)
        choices = self.policy.select(self.capabilities, request) if self.capabilities else []
        return {"mode": mode, "task_profile": request.task_profile, "selected": choices[0][0].__dict__ if choices else None,
                "reason": choices[0][1] if choices else "no compatible configured model", "fallback_active": len(choices) > 1}

    def plan_task(self, user_input: str) -> dict[str, Any]:
        task_route = self.classify_task(user_input)
        route_config = self.config.get("task_routes", {}).get(task_route, {})
        model_key = route_config.get("use_model", "fast_chat")
        model_config = self.config.get("models", {}).get(model_key, {})
        return {
            "task_route": task_route,
            "route_config": route_config,
            "model_key": model_key,
            "model_config": model_config,
        }

    def build_cache_key(self, user_input: str, plan: dict[str, Any]) -> str:
        return self.cache.make_key(
            {
                "task_route": plan["task_route"],
                "model_key": plan["model_key"],
                "input": user_input.strip(),
            }
        )

    def _read_json(self, path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return default

    def _write_json(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _fallback_config(self) -> dict[str, Any]:
        return self.config.get("fallback", {})

    def _now(self) -> datetime:
        return datetime.now(UTC)

    def _cooldown_key(self, provider: str, model: str) -> str:
        return f"{provider}::{model}"

    def _cooldown_state(self) -> dict[str, Any]:
        state = self._read_json(self.cooldown_state_path, {})
        return state if isinstance(state, dict) else {}

    def _save_cooldown_state(self, state: dict[str, Any]) -> None:
        self._write_json(self.cooldown_state_path, state)

    def _has_active_cooldowns(self) -> bool:
        return any(self._cooldown_entry(*key.split("::", 1)) for key in self._cooldown_state().keys() if "::" in key)

    def _set_cooldown(self, provider: str, model: str, reason: str, seconds: int) -> None:
        if seconds <= 0:
            return
        state = self._cooldown_state()
        state[self._cooldown_key(provider, model)] = {
            "provider": provider,
            "model": model,
            "reason": reason,
            "until": time.time() + seconds,
            "seconds": seconds,
        }
        self._save_cooldown_state(state)

    def _cooldown_entry(self, provider: str, model: str) -> dict[str, Any] | None:
        state = self._cooldown_state()
        entry = state.get(self._cooldown_key(provider, model))
        if not isinstance(entry, dict):
            return None
        if float(entry.get("until", 0)) <= time.time():
            state.pop(self._cooldown_key(provider, model), None)
            self._save_cooldown_state(state)
            return None
        return entry

    def _cooldown_remaining_seconds(self, provider: str, model: str) -> int:
        entry = self._cooldown_entry(provider, model)
        if not entry:
            return 0
        return max(int(float(entry.get("until", 0)) - time.time()), 0)

    def _default_temporary_cooldown(self) -> int:
        return int(self._fallback_config().get("temporary_failure_cooldown_seconds", 300))

    def _default_auth_cooldown(self) -> int:
        return int(self._fallback_config().get("authentication_failure_cooldown_seconds", 300))

    def _openrouter_free_models(self) -> list[str]:
        fallback = self._fallback_config().get("openrouter_free_models")
        if isinstance(fallback, list) and fallback:
            return [self._coerce_model_name(item) for item in fallback if self._coerce_model_name(item)]
        legacy = self.config.get("cloud_unlock", {}).get("allowed_models_when_unlocked", [])
        return [self._coerce_model_name(item) for item in legacy if self._coerce_model_name(item)]

    @staticmethod
    def _coerce_model_name(item: Any) -> str:
        if isinstance(item, dict) and len(item) == 1:
            key, value = next(iter(item.items()))
            return f"{str(key).strip().strip(chr(34))}:{str(value).strip().strip(chr(34))}"
        return str(item).strip()

    def _ollama_models(self) -> list[str]:
        models = self._fallback_config().get("ollama_models", ["llama3.2:3b"])
        ordered = [self._coerce_model_name(item) for item in models if self._coerce_model_name(item)]
        if "llama3.2:3b" in ordered:
            ordered = ["llama3.2:3b", *[item for item in ordered if item != "llama3.2:3b"]]
        return ordered

    @staticmethod
    def _is_local_provider(provider_name: str) -> bool:
        return provider_name in {"ollama", "lmstudio_windows", "llama_cpp_server", "mlx_mac"}

    @staticmethod
    def _should_force_local_fallback(failure_reason: str) -> bool:
        normalized = str(failure_reason or "").strip().lower()
        return any(
            token in normalized
            for token in (
                "http_402",
                "payment_required",
                "payment required",
                "insufficient_credits",
                "insufficient credits",
                "quota exceeded",
                "exhausted_quota",
                "credit balance exhausted",
                "provider_unavailable",
                "provider unavailable",
            )
        )

    def _primary_cloud_provider_name(self, runtime_config: dict[str, Any]) -> str | None:
        provider = str(runtime_config.get("llm", {}).get("provider", "")).strip().lower()
        if not runtime_config.get("cloud_enabled"):
            return None
        if provider in {"", "stub", "local", "local_router", "lmstudio", "lm_studio", "ollama"}:
            return None
        return provider

    def _primary_cloud_base_url(self, provider_name: str, runtime_config: dict[str, Any]) -> str:
        configured = str(runtime_config.get("llm", {}).get("base_url", "")).strip()
        if configured:
            return configured.rstrip("/")
        if provider_name == "openrouter":
            return "https://openrouter.ai/api/v1"
        return "https://api.openai.com/v1"

    def _provider_probe(self, provider_name: str, provider_config: dict[str, Any]) -> bool:
        base_url = str(provider_config.get("base_url", "")).rstrip("/")
        if not base_url:
            return False
        targets = []
        if provider_name == "ollama":
            targets = [f"{base_url}/api/tags", f"{base_url}/v1/models"]
        elif base_url.endswith("/v1"):
            targets = [f"{base_url}/models"]
        else:
            targets = [base_url, f"{base_url}/models"]
        for target in targets:
            try:
                request = urllib.request.Request(target, method="GET")
                with urllib.request.urlopen(request, timeout=0.4) as response:
                    if 200 <= getattr(response, "status", 200) < 500:
                        return True
            except urllib.error.HTTPError as exc:
                if exc.code < 500:
                    return True
            except Exception:
                continue
        return False

    def _ollama_provider_config(self) -> dict[str, Any]:
        configured = self.provider_registry.providers().get("ollama", {})
        if configured:
            return dict(configured)
        return {
            "enabled": True,
            "type": "ollama_local",
            "base_url": "http://127.0.0.1:11434",
            "request_timeout_seconds": 120,
            "model_discovery_timeout_seconds": 2,
            "cost": 0,
        }

    def _build_attempt(
        self,
        provider_name: str,
        provider_config: dict[str, Any],
        model: str,
        plan: dict[str, Any],
        memory: Any,
        repo_index: Any,
    ) -> dict[str, Any]:
        return {
            "provider": {"name": provider_name, "provider": provider_config},
            "model": model,
            "task_route": plan["task_route"],
            "model_key": plan["model_key"],
            "memory": memory,
            "repo_index": repo_index,
            "params": plan["model_config"].get("params", {}),
        }

    def _candidate_attempts(
        self,
        plan: dict[str, Any],
        runtime_config: dict[str, Any],
        memory: Any,
        repo_index: Any,
    ) -> list[dict[str, Any]]:
        attempts: list[dict[str, Any]] = []
        primary = self._primary_cloud_provider_name(runtime_config)
        if primary:
            attempts.append(
                self._build_attempt(
                    primary,
                    {
                        "base_url": self._primary_cloud_base_url(primary, runtime_config),
                        "env_key": "OPENROUTER_API_KEY" if primary == "openrouter" else "OPENAI_API_KEY",
                        "request_timeout_seconds": int(runtime_config.get("limits", {}).get("request_timeout_seconds", 60)),
                        "cost": "paid",
                    },
                    str(runtime_config.get("llm", {}).get("model", "")).strip() or "gpt-4o-mini",
                    plan,
                    memory,
                    repo_index,
                )
            )

        if runtime_config.get("cloud_enabled"):
            for model in self._openrouter_free_models():
                attempts.append(
                    self._build_attempt(
                        "openrouter_free",
                        {
                            "base_url": "https://openrouter.ai/api/v1",
                            "env_key": "OPENROUTER_API_KEY",
                            "request_timeout_seconds": int(runtime_config.get("limits", {}).get("request_timeout_seconds", 60)),
                            "cost": 0,
                        },
                        model,
                        plan,
                        memory,
                        repo_index,
                    )
                )

        for model in self._ollama_models():
            attempts.append(
                self._build_attempt(
                    "ollama",
                    self._ollama_provider_config(),
                    model,
                    plan,
                    memory,
                    repo_index,
                )
            )

        mode = self.routing_mode(runtime_config)
        preferred_provider = str(runtime_config.get("preferred_provider", "")).strip()
        preferred_model = str(runtime_config.get("preferred_model") or runtime_config.get("llm", {}).get("model", "")).strip()
        local_only = bool(runtime_config.get("local_only", self.config.get("local_only", False)))
        if local_only:
            attempts = [item for item in attempts if item["provider"]["name"] in {"ollama", "lmstudio_windows", "llama_cpp_server", "mlx_mac"}]
        if preferred_model:
            preferred = [item for item in attempts if item["model"] == preferred_model and (not preferred_provider or item["provider"]["name"] == preferred_provider)]
            attempts = preferred + [item for item in attempts if item not in preferred]
        if mode == RoutingMode.MANUAL.value and not runtime_config.get("emergency_fallback"):
            attempts = attempts[:1]

        seen: set[tuple[str, str]] = set()
        unique_attempts: list[dict[str, Any]] = []
        for attempt in attempts:
            key = (attempt["provider"]["name"], attempt["model"])
            if key in seen:
                continue
            seen.add(key)
            unique_attempts.append(attempt)
        return unique_attempts

    def _normalize_exception_failure(self, exc: Exception) -> dict[str, Any]:
        message = str(exc).lower()
        if isinstance(exc, TimeoutError):
            return {"failure_reason": "timeout", "retryable": True, "cooldown_seconds": self._default_temporary_cooldown()}
        if isinstance(exc, OSError):
            if "timed out" in message:
                return {"failure_reason": "timeout", "retryable": True, "cooldown_seconds": self._default_temporary_cooldown()}
            if "auth" in message:
                return {"failure_reason": "authentication_failed", "retryable": False, "cooldown_seconds": self._default_auth_cooldown()}
            if "unavailable" in message:
                return {"failure_reason": "provider_unavailable", "retryable": True, "cooldown_seconds": self._default_temporary_cooldown()}
            return {"failure_reason": "connection_failure", "retryable": True, "cooldown_seconds": self._default_temporary_cooldown()}
        return {"failure_reason": "provider_unavailable", "retryable": True, "cooldown_seconds": self._default_temporary_cooldown()}

    def _normalize_failure_result(self, result: dict[str, Any] | None) -> dict[str, Any]:
        if not isinstance(result, dict):
            return {"failure_reason": "provider_unavailable", "retryable": True, "cooldown_seconds": self._default_temporary_cooldown()}
        if "failure_reason" in result:
            return {
                "failure_reason": str(result.get("failure_reason")),
                "retryable": bool(result.get("retryable", True)),
                "cooldown_seconds": int(
                    result.get(
                        "cooldown_seconds",
                        self._default_auth_cooldown() if str(result.get("failure_reason")) == "authentication_failed" else self._default_temporary_cooldown(),
                    )
                ),
            }
        if result.get("error"):
            return {"failure_reason": str(result["error"]), "retryable": True, "cooldown_seconds": self._default_temporary_cooldown()}
        return {"failure_reason": "provider_unavailable", "retryable": True, "cooldown_seconds": self._default_temporary_cooldown()}

    def _append_audit_log(self, entry: dict[str, Any]) -> None:
        entries = self._read_json(self.audit_log_path, [])
        if not isinstance(entries, list):
            entries = []
        entries.append(entry)
        self._write_json(self.audit_log_path, entries)

    def _latest_audit_entry(self) -> dict[str, Any] | None:
        entries = self._read_json(self.audit_log_path, [])
        if isinstance(entries, list) and entries:
            last = entries[-1]
            if isinstance(last, dict):
                return last
        return None

    def _fallback_notice(self, attempts: list[dict[str, Any]], final_provider: str, final_model: str) -> str | None:
        failed = [attempt["provider"] for attempt in attempts if attempt.get("outcome") == "failed"]
        if not failed:
            return None
        chain = " -> ".join([*failed, f"{final_provider}/{final_model}"])
        return f"Fallback used: {chain}."

    def _error_response(
        self,
        plan: dict[str, Any],
        audit_attempts: list[dict[str, Any]],
        forced_local_notice: str | None = None,
    ) -> dict[str, Any]:
        self.credit_guard.complete_task()
        notice = forced_local_notice
        if notice is None and audit_attempts:
            last = audit_attempts[-1]
            notice = self._fallback_notice(audit_attempts, str(last.get("provider")), str(last.get("model")))
        message = "Local models were selected first, but no local model completed the task."
        if forced_local_notice:
            message = self.CLOUD_FALLBACK_UNAVAILABLE_MESSAGE
        return {
            "error": "local-runtime-missing",
            "message": message,
            "task_route": plan["task_route"],
            "unlock_phrase": CLOUD_UNLOCK_PHRASE,
            "fallback_notice": notice,
        }

    def run_task(
        self,
        user_input: str,
        model_inference: Callable[[dict[str, Any]], dict[str, Any] | None],
        mentioned_files: list[str] | None = None,
        unlock_phrase: str | None = None,
        runtime_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if unlock_phrase:
            self.credit_guard.unlock_for_task(unlock_phrase)

        runtime_config = runtime_config or {}
        plan = self.plan_task(user_input)
        cache_key = self.build_cache_key(user_input, plan)
        cache_payload = {"input": user_input, "plan": plan}
        cached = None if self._has_active_cooldowns() else self.cache.get_cached_response(cache_key, cache_payload)
        if cached is not None:
            self.credit_guard.complete_task()
            if isinstance(cached, dict) and "result" in cached:
                return {"source": "cache", **cached}
            return {"source": "cache", "result": cached}

        memory = self.memory_reader(plan) if self.config.get("routing", {}).get("memory_before_model", True) else {}
        repo_index = None
        if plan["task_route"] in {"repo_debug", "code_patch"}:
            repo_index = self.repo_indexer.build_index(startup=False, mentioned_files=mentioned_files or [])

        audit_attempts: list[dict[str, Any]] = []
        forced_local_notice: str | None = None
        attempts = self._candidate_attempts(plan, runtime_config, memory, repo_index)
        if not attempts:
            return self._error_response(plan, audit_attempts, forced_local_notice)

        for attempt in attempts:
            provider_name = attempt["provider"]["name"]
            model_name = attempt["model"]
            if forced_local_notice and not self._is_local_provider(provider_name):
                audit_attempts.append(
                    {
                        "provider": provider_name,
                        "model": model_name,
                        "outcome": "skipped",
                        "failure_reason": "forced_local_fallback",
                        "fallback_decision": "switch to local ollama",
                        "latency_ms": 0,
                    }
                )
                continue
            cooldown_remaining = self._cooldown_remaining_seconds(provider_name, model_name)
            if cooldown_remaining > 0:
                audit_attempts.append(
                    {
                        "provider": provider_name,
                        "model": model_name,
                        "outcome": "skipped",
                        "failure_reason": "cooldown_active",
                        "fallback_decision": f"skip provider for {cooldown_remaining}s cooldown",
                        "latency_ms": 0,
                    }
                )
                continue

            if self._is_local_provider(provider_name) and not runtime_config.get("cloud_enabled") and not self.provider_registry._probe_provider(provider_name, attempt["provider"]["provider"]):
                audit_attempts.append(
                    {
                        "provider": provider_name,
                        "model": model_name,
                        "outcome": "failed",
                        "failure_reason": "provider_unavailable",
                        "fallback_decision": "retry on next provider",
                        "latency_ms": 0,
                    }
                )
                self._set_cooldown(provider_name, model_name, "provider_unavailable", self._default_temporary_cooldown())
                continue

            started = time.perf_counter()
            attempt["request_id"] = str(runtime_config.get("request_id", "hermes-request"))
            attempt["idempotency_key"] = str(runtime_config.get("idempotency_key", attempt["request_id"]))
            try:
                result = model_inference(attempt)
            except Exception as exc:  # pragma: no cover - defensive classification
                result = {"error": "provider-failure", **self._normalize_exception_failure(exc)}
            latency_ms = int((time.perf_counter() - started) * 1000)

            if result and result.get("result"):
                notice = forced_local_notice or self._fallback_notice(audit_attempts, provider_name, model_name)
                response = {
                    "source": "model",
                    **result,
                    "task_route": plan["task_route"],
                    "model_key": plan["model_key"],
                }
                if notice:
                    response["fallback_notice"] = notice
                self.cache.set_model_output(cache_key, response, cache_payload)
                self.credit_guard.complete_task()
                self._append_audit_log(
                    {
                        "timestamp": self._now().isoformat(),
                        "task_route": plan["task_route"],
                        "model_key": plan["model_key"],
                        "final_provider": provider_name,
                        "final_model": model_name,
                        "final_status": "success",
                        "latency_ms": latency_ms,
                        "fallback_notice": notice,
                        "attempts": [
                            *audit_attempts,
                            {
                                "provider": provider_name,
                                "model": model_name,
                                "outcome": "success",
                                "failure_reason": None,
                                "fallback_decision": "completed request",
                                "latency_ms": latency_ms,
                            },
                        ],
                    }
                )
                return response

            failure = self._normalize_failure_result(result)
            fallback_decision = "retry on next provider"
            if not self._is_local_provider(provider_name) and self._should_force_local_fallback(failure["failure_reason"]):
                forced_local_notice = self.CLOUD_FALLBACK_NOTICE
                fallback_decision = "switch to local ollama"
            audit_attempts.append(
                {
                    "provider": provider_name,
                    "model": model_name,
                    "outcome": "failed",
                    "failure_reason": failure["failure_reason"],
                    "fallback_decision": fallback_decision,
                    "latency_ms": latency_ms,
                }
            )
            self._set_cooldown(provider_name, model_name, failure["failure_reason"], int(failure["cooldown_seconds"]))

        error_response = self._error_response(plan, audit_attempts, forced_local_notice)
        self._append_audit_log(
            {
                "timestamp": self._now().isoformat(),
                "task_route": plan["task_route"],
                "model_key": plan["model_key"],
                "final_provider": None,
                "final_model": None,
                "final_status": "failed",
                "latency_ms": 0,
                "fallback_notice": error_response.get("fallback_notice"),
                "attempts": audit_attempts,
            }
        )
        return error_response

    def provider_health(self, runtime_config: dict[str, Any] | None = None) -> dict[str, Any]:
        runtime_config = runtime_config or {}
        plan = {
            "task_route": "simple_chat",
            "model_key": "fast_chat",
            "model_config": self.config.get("models", {}).get("fast_chat", {}),
        }
        attempts = self._candidate_attempts(plan, runtime_config, memory={}, repo_index=None)
        providers: list[dict[str, Any]] = []
        for attempt in attempts:
            provider_name = attempt["provider"]["name"]
            model_name = attempt["model"]
            cooldown_entry = self._cooldown_entry(provider_name, model_name)
            available = True
            if provider_name == "ollama":
                available = self._provider_probe(provider_name, attempt["provider"]["provider"])
            elif provider_name in {"openai", "openrouter", "openrouter_free"}:
                env_key = str(attempt["provider"]["provider"].get("env_key", "")).strip()
                available = bool(runtime_config.get("cloud_enabled")) and bool(env_key)
            provider_payload = {
                "provider": provider_name,
                "model": model_name,
                "available": bool(available and not cooldown_entry),
                "cooldown_remaining_seconds": self._cooldown_remaining_seconds(provider_name, model_name),
                "last_error": cooldown_entry.get("reason") if cooldown_entry else None,
            }
            providers.append(provider_payload)

        latest = self._latest_audit_entry()
        selected = self.route_request("status check", runtime_config).get("selected")
        ollama_attempt = next(
            (item for item in attempts if item["provider"]["name"] == "ollama" and item.get("model") == "llama3.2:3b"),
            None,
        )
        if ollama_attempt and any(item.get("provider") == "ollama" and item.get("available") for item in providers):
            selected = {"provider": "ollama", "model_id": "llama3.2:3b", "local": True}
        return {
            "router_status": "degraded" if any(item.get("cooldown_remaining_seconds", 0) for item in providers) else "healthy",
            "active_mode": self.routing_mode(runtime_config),
            "selected_provider": selected.get("provider") if isinstance(selected, dict) else None,
            "selected_model": selected.get("model_id") if isinstance(selected, dict) else None,
            "execution_scope": "local" if selected and selected.get("local") else "cloud",
            "available_providers": sorted({str(item["provider"]) for item in providers if item.get("available")}),
            "local_ollama_available": any(item.get("provider") == "ollama" and item.get("available") for item in providers),
            "fallback_active": bool(latest and latest.get("fallback_notice")) if latest else False,
            "providers": providers,
            "last_fallback_notice": latest.get("fallback_notice") if latest else None,
            "fallback_reason": latest.get("fallback_notice") if latest else None,
        }
