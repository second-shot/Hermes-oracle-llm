import json
from core.router import route_task
from core.prompt_compressor import compress
from llm.client import call_model
from memory.store import read_memory, update_memory
from core.cache import make_key, get_exact, set_exact, get_semantic, set_semantic


def execute_task(user_input, config):
    compressed = compress(user_input)

    # Check exact cache
    packet_str = json.dumps(compressed, sort_keys=True)
    cache_key = make_key(packet_str)
    cached_exact = get_exact(cache_key)
    if cached_exact is not None:
        response = {"result": cached_exact, "cache": "exact_hit"}
        update_memory(compressed, response)
        return response

    # Check semantic cache
    cached_semantic = get_semantic(compressed)
    if cached_semantic is not None:
        response = {"result": cached_semantic, "cache": "semantic_hit"}
        update_memory(compressed, response)
        return response

    # Otherwise, we need to call the model
    task_type = compressed["task_type"]
    route = route_task(task_type, config)
    memory = read_memory(compressed)

    prompt = {
        "task": compressed,
        "memory": memory
    }

    response = None
    retries = 0
    max_retries = config["limits"]["max_retries_local"]

    while retries <= max_retries:
        response = call_model(prompt, route, config)

        if response and len(str(response)) > 0:
            break

        retries += 1

    if not response:
        return {"error": "failed_execution", "cache": "miss"}

    # Now we have the model response, which is a dict with "result"
    response_str = response["result"]

    # Update memory
    update_memory(compressed, {"result": response_str})

    # Store in cache
    set_exact(cache_key, response_str)
    set_semantic(compressed, response_str)

    return {"result": response_str, "cache": "miss"}