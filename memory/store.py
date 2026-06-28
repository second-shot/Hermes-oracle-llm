from datetime import datetime
from pathlib import Path

from runtime_state import append_text, atomic_write_json, ensure_runtime_state


REPO_ROOT = Path(__file__).resolve().parents[1]


def _runtime_paths():
    runtime = ensure_runtime_state(REPO_ROOT)
    return runtime.memory_dir / "structured.json", runtime.logs_dir / "sessions.md"


def read_memory(prompt):
    structured_path, _ = _runtime_paths()
    try:
        import json

        with structured_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, OSError, ValueError):
        return {}


def update_memory(prompt, response):
    structured_path, _ = _runtime_paths()
    data = read_memory(prompt)

    key = prompt["task_type"]
    data[key] = response

    atomic_write_json(structured_path, data)


def log_session(user_input, output):
    _, log_path = _runtime_paths()
    append_text(
        log_path,
        f"\n[{datetime.now()}]\nINPUT: {user_input}\nOUTPUT: {output}\n",
        redact=True,
    )
