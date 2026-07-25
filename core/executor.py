import json
import os
from core.prompt_compressor import compress
from llm.client import call_model
from llm.free_remote import call_free_remote
from memory.store import read_memory, update_memory
from backend.services.model_router import ModelRouter


CACHE_SCHEMA_VERSION = "hermes-cache-v2-provider-adapter"


def _provider_name(config):
    return (
        os.environ.get("HERMES_LLM_PROVIDER")
        or config.get("llm", {}).get("provider")
        or "stub"
    ).lower()


def execute_task(user_input, config):
    compressed = compress(user_input)
    prompt = {"task": compressed}
    router = ModelRouter(memory_reader=lambda _plan: read_memory(compressed))

    def infer(attempt):
        provider_status = attempt["provider"]
        is_free_remote = bool(provider_status.get("is_cloud"))
        provider_name = provider_status["name"]
        provider_config = provider_status["provider"]
        prompt["memory"] = attempt.get("memory", {})
        prompt["repo_index"] = attempt.get("repo_index")

        if is_free_remote:
            return call_free_remote(
                prompt,
                provider_name,
                provider_config,
                attempt["model"],
                attempt.get("params", {}),
            )

        attempt_route = {
            "kind": "local",
            "provider": provider_name,
            "provider_config": provider_config,
            "model": attempt["model"],
            "task_route": attempt["task_route"],
            "params": attempt.get("params", {}),
        }
        return call_model(prompt, attempt_route, config)

    result = router.run_task(user_input, infer)
    if result.get("error"):
        return {
            "error": result["error"],
            "message": result.get("message"),
            "fallback_status": result.get("fallback_status"),
            "cache": "miss",
        }

    response = {
        "result": result["result"],
        "route_class": result.get("route_class", "cache"),
        "cache": "hit" if result["source"] == "cache" else "miss",
    }
    update_memory(compressed, response)
    return response
