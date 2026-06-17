import os

MODEL_PATH = os.environ.get("HERMES_MODEL_PATH", "models/model.gguf")

try:
    from llama_cpp import Llama
except Exception:  # keeps Hermes bootable when dependency is missing
    Llama = None

llm = None


def _fallback_response(prompt, reason):
    task = prompt.get("task", {})
    goal = task.get("goal", "")
    task_type = task.get("task_type", "unknown")
    compressed = task.get("compressed_prompt", "")

    return {
        "result