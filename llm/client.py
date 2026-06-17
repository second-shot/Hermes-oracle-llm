import os


DEFAULT_PROVIDER = "stub"


def _provider(config):
    return (
        os.environ.get("HERMES_LLM_PROVIDER")
        or config.get("llm", {}).get("provider")
        or DEFAULT_PROVIDER
    ).lower()


def _compressed_task(prompt):
    task = prompt.get("task", {}) if isinstance(prompt, dict) else {}
    return {
        "goal": task.get("goal", ""),
        "task_type": task.get("task_type", "unknown"),
        "compressed_prompt": task.get("compressed_prompt", ""),
        "entities": task.get("entities", []),
        "constraints": task.get("constraints", []),
    }


def _stub_response(prompt, reason="no model provider configured"):
    task = _compressed_task(prompt)
    goal = task["goal"].strip()

    if goal.lower().startswith("task: create first resale workflow"):
        result = (
            "HERMES STUB MODE\n"
            "Workflow: first resale workflow\n\n"
            "1. CAPTURE: photograph item front, back, label, damage, size, material.\n"
            "2. CLASSIFY: category, brand, condition, resale platform.\n"
            "3. PRICE: low / fair / stretch price.\n"
            "4. ROUTE: quick-sale items to Vinted, higher-value items to eBay, rare/designer to research queue.\n"
            "5. LIST: title, 5 bullet description, condition note, price, shipping status.\n"
            "6. DECIDE: NOW if value is clear, PREP if needs cleaning/photos, HOLD if value unknown, EXIT if not worth time.\n"
            "7. LOG: save item, price, platform, next action, and result."
        )
    else:
        result = (
            "HERMES STUB MODE\n"
            f"Reason: {reason}\n"
            f"Task type: {task['task_type']}\n"
            f"Goal: {task['goal']}\n"
            f"Compressed input: {task['compressed_prompt']}\n\n"
            "No external LLM is active. Hermes is running routing, memory, cache, and deterministic fallback logic."
        )

    return {
        "result": result,
        "meta": {
            "mode": "stub",
            "reason": reason,
            "provider": "stub",
        },
    }


def _mlx_response(prompt, config):
    return _stub_response(
        prompt,
        "MLX provider selected but not implemented yet. Add mlx-lm runtime when ready.",
    )


def _openrouter_response(prompt, config):
    return _stub_response(
        prompt,
        "OpenRouter provider selected but not implemented yet. Add API client and key when ready.",
    )


def _ollama_response(prompt, config):
    return _stub_response(
        prompt,
        "Ollama provider selected but not implemented yet. Add local HTTP client when ready.",
    )


def call_model(prompt, route, config):
    if route != "local":
        return _stub_response(prompt, f"route '{route}' is not implemented")

    provider = _provider(config)

    if provider == "stub":
        return _stub_response(prompt)
    if provider == "mlx":
        return _mlx_response(prompt, config)
    if provider == "openrouter":
        return _openrouter_response(prompt, config)
    if provider == "ollama":
        return _ollama_response(prompt, config)

    return _stub_response(prompt, f"unknown provider '{provider}'")
