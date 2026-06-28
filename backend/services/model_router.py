from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from backend.services.credit_guard import CLOUD_UNLOCK_PHRASE, CreditGuard
from backend.services.local_cache import LocalCache
from backend.services.provider_registry import DEFAULT_CONFIG_PATH, ProviderRegistry, load_rotation_config
from backend.services.repo_indexer import RepoIndexer


class ModelRouter:
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

    def _candidate_attempts(self, plan: dict[str, Any], providers: list[Any], memory: Any, repo_index: Any) -> list[dict[str, Any]]:
        model_candidates = plan["model_config"].get("model_candidates", [])
        attempts: list[dict[str, Any]] = []
        for provider in providers:
            for model_name in model_candidates:
                attempts.append(
                    {
                        "provider": provider.__dict__,
                        "model": model_name,
                        "task_route": plan["task_route"],
                        "model_key": plan["model_key"],
                        "memory": memory,
                        "repo_index": repo_index,
                        "params": plan["model_config"].get("params", {}),
                    }
                )
        return attempts[:2]

    def run_task(
        self,
        user_input: str,
        model_inference: Callable[[dict[str, Any]], dict[str, Any] | None],
        mentioned_files: list[str] | None = None,
        unlock_phrase: str | None = None,
    ) -> dict[str, Any]:
        if unlock_phrase:
            self.credit_guard.unlock_for_task(unlock_phrase)

        plan = self.plan_task(user_input)
        cache_key = self.build_cache_key(user_input, plan)
        cache_payload = {"input": user_input, "plan": plan}
        cached = self.cache.get_cached_response(cache_key, cache_payload)
        if cached is not None:
            self.credit_guard.complete_task()
            if isinstance(cached, dict) and "result" in cached:
                return {"source": "cache", **cached}
            return {"source": "cache", "result": cached}

        memory = self.memory_reader(plan) if self.config.get("routing", {}).get("memory_before_model", True) else {}
        repo_index = None
        if plan["task_route"] in {"repo_debug", "code_patch"}:
            repo_index = self.repo_indexer.build_index(startup=False, mentioned_files=mentioned_files or [])

        providers = self.provider_registry.available_providers(plan["task_route"], plan["model_key"], self.credit_guard)
        local_providers = [provider for provider in providers if not provider.is_cloud]
        if not local_providers:
            self.credit_guard.complete_task()
            return {
                "error": "local-runtime-missing",
                "message": "No local runtime is available. Start LM Studio or llama.cpp and try again.",
                "task_route": plan["task_route"],
            }

        for attempt in self._candidate_attempts(plan, local_providers, memory, repo_index):
            result = model_inference(attempt)
            if result and result.get("result"):
                self.cache.set_model_output(cache_key, result, cache_payload)
                self.credit_guard.complete_task()
                return {"source": "model", **result, "task_route": plan["task_route"], "model_key": plan["model_key"]}

        self.credit_guard.complete_task()
        return {
            "error": "local-runtime-missing",
            "message": "Local models were selected first, but no local model completed the task.",
            "task_route": plan["task_route"],
            "unlock_phrase": CLOUD_UNLOCK_PHRASE,
        }
