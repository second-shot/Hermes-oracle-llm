import json
import sys

from core.executor import execute_task
from downloads.cli import handle_download_command, print_json
from memory.store import log_session


def load_config():
    with open("config.json", "r") as f:
        return json.load(f)


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
