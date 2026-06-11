def classify_task(text):
    t = text.lower()


    if "image" in t:
        return "vision"
    if any(k in t for k in ["code", "function", "bug", "script"]):
        return "coding"
    if any(k in t for k in ["plan", "design", "build"]):
        return "text_reasoning"
    if any(k in t for k in ["save", "remember", "memory"]):
        return "memory"
    if any(k in t for k in ["search", "find", "retrieve"]):
        return "retrieval"
    if any(k in t for k in ["auto", "automation"]):
        return "automation"


    return "text_reasoning"


def route_task(task_type, config):
    if config.get("cloud_enabled") is True and task_type == "vision":
        return "cloud"


    return "local"