import json
import sys
from pathlib import Path

from core.executor import execute_task
from downloads.cli import handle_download_command, print_json
from memory.store import log_session


ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
DEFAULT_CONFIG = {
    "primary_model": "stub",
    "cloud_enabled": False,
    "llm": {
        "provider": "stub",
        "model": "stub",
        "temperature": 0.2,
        "api_key": "",
    },
    "routing": {
        "vision": "local",
        "text_reasoning": "local",
        "coding": "local",
        "automation": "local",
        "memory": "local",
        "retrieval": "local",
    },
    "limits": {
        "max_retries_local": 2,
        "max_retries_cloud": 1,
        "max_tokens": {
            "text_reasoning": 100,
            "coding": 200,
            "automation": 50,
            "memory": 50,
            "retrieval": 50,
            "vision": 150,
        },
    },
}


def _merge_config(defaults, overrides):
    merged = dict(defaults)
    for key, value in overrides.items():
        default_value = merged.get(key)
        if isinstance(default_value, dict) and isinstance(value, dict):
            merged[key] = _merge_config(default_value, value)
        else:
            merged[key] = value
    return merged


def load_config():
    if not CONFIG_PATH.exists():
        return json.loads(json.dumps(DEFAULT_CONFIG))

    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        loaded = json.load(f)

    return _merge_config(DEFAULT_CONFIG, loaded)


def run_interactive(config):
    print("HERMES ACTIVE (deterministic mode)")
    print("Type 'exit' to stop")
    print("Blank input is ignored")
    print("Use: download scan | download status | download queue")

    while True:
        user_input = input("\n> ").strip()

        if not user_input:
            continue

        if user_input.lower() == "exit":
            break

        if user_input.lower().startswith("download"):
            result = handle_download_command(user_input.split()[1:])
        else:
            result = execute_task(user_input, config)

        print("\nOUTPUT:\n", result)
        log_session(user_input, result)


def main():
    config = load_config()

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command in {"download", "downloads"}:
            result = handle_download_command(sys.argv[2:])
            print_json(result)
            return

    run_interactive(config)


if __name__ == "__main__":
    main()
