from core.prompt_compressor import compress
from llm.client import call_model
from memory.store import read_memory, update_memory
from backend.services.model_router import ModelRouter


CACHE_SCHEMA_VERSION = "hermes-cache-v2-provider-adapter"


def execute_task(user_input, config):
    compressed = compress(user_input)

    # Compression is internal routing metadata, not the conversational prompt.
    # Local chat models should see the user's natural-language request exactly
    # as entered. Feeding the T:/G:/E:/C: packet to small local models can change
    # the meaning of otherwise simple instructions and trigger bad responses.
    model_task = dict(compressed)
    model_task["compressed_prompt"] = user_input.strip()
    prompt = {"task": model_task}

    # Simple chat should not inherit the entire persistent memory store. Keep
    # memory available for task classes that can benefit from project context,
    # while preventing stale prior outputs from overriding fresh chat requests.
    def memory_for_plan(plan):
        if plan.get("task_route") == "simple_chat":
            return {}
        return read_memory(compressed)

    router = ModelRouter(memory_reader=memory_for_plan)

    def infer(attempt):
        attempt_route = {
            "kind": "local",
            "provider": attempt["provider"]["name"],
            "provider_config": attempt["provider"]["provider"],
            "model": attempt["model"],
            "task_route": attempt["task_route"],
            "params": attempt.get("params", {}),
        }
        prompt["memory"] = attempt.get("memory", {})
        prompt["repo_index"] = attempt.get("repo_index")
        return call_model(prompt, attempt_route, config)

    result = router.run_task(user_input, infer, runtime_config=config)
    if result.get("error"):
        if result["error"] == "local-runtime-missing" and config.get("cloud_enabled") is True and not result.get("fallback_notice"):
            fallback = call_model(prompt, "local", config)
            if fallback and fallback.get("result"):
                response = {"result": fallback["result"], "cache": "miss"}
                update_memory(compressed, response)
                return response
        return {
            "error": result["error"],
            "message": result.get("message"),
            "cache": "miss",
            "fallback_notice": result.get("fallback_notice"),
        }

    response = {"result": result["result"], "cache": "hit" if result["source"] == "cache" else "miss"}
    if result.get("meta"):
        response["meta"] = result["meta"]
    if result.get("fallback_notice"):
        response["fallback_notice"] = result["fallback_notice"]
    update_memory(compressed, response)
    return response
