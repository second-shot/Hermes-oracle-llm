import os

MODEL_PATH = os.environ.get("HERMES_MODEL_PATH", "models/model.gguf")

try:
    from llama_cpp import Llama
except Exception:
    Llama = None

llm = None


def _fallback_response(prompt, reason):
    task = prompt.get("task", {})
    goal = task.get("goal", "")
    task_type = task.get("task_type", "unknown")
    compressed = task.get("compressed_prompt", "")

    return {
        "result": (
            "HERMES BOOTSAFE MODE\n"
            f"Reason: {reason}\n"
            f"Task type: {task_type}\n"
            f"Goal: {goal}\n"
            f"Compressed input: {compressed}\n\n"
            "Local model execution is not available yet. "
            "Hermes is running its routing, memory, and cache spine without the GGUF model."
        ),
        "meta": {
            "mode": "bootsafe",
            "reason": reason,
            "model_path": MODEL_PATH,
        },
    }


def _load_llm(config):
    global llm

    if llm is not None:
        return llm

    if Llama is None:
        raise RuntimeError("llama_cpp is not installed")

    if not os.path.exists(MODEL_PATH):
        raise FileNotFoundError(f"model file not found: {MODEL_PATH}")

    local_config = config.get("models", {}).get("local", {})
    llm = Llama(
        model_path=MODEL_PATH,
        n_ctx=local_config.get("context", 2048),
        n_threads=local_config.get("threads", 4),
        n_batch=local_config.get("batch", 128),
        verbose=False,
    )
    return llm


def call_model(prompt, route, config):
    if route != "local":
        return _fallback_response(prompt, f"route '{route}' is not implemented")

    try:
        model = _load_llm(config)
    except Exception as exc:
        return _fallback_response(prompt, str(exc))

    local_config = config.get("models", {}).get("local", {})
    max_tokens = local_config.get("max_tokens", 200)
    temperature = local_config.get("temperature", 0.2)

    text_prompt = (
        "You are Hermes, a concise deterministic local assistant.\n"
        f"Task: {prompt}\n"
        "Answer clearly and briefly."
    )

    output = model(
        text_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        stop=["</s>", "User:"],
    )

    return {
        "result": output["choices"][0]["text"].strip(),
        "meta": {
            "mode": "local_llama_cpp",
            "model_path": MODEL_PATH,
        },
    }
