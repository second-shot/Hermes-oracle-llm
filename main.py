import json
from core.executor import execute_task
from memory.store import log_session


def load_config():
    with open("config.json", "r") as f:
        return json.load(f)


def main():
    config = load_config()


    print("HERMES ACTIVE (deterministic mode)")
    print("Type 'exit' to stop")


    while True:
        user_input = input("\n> ")


        if user_input.lower() == "exit":
            break


        result = execute_task(user_input, config)
        print("\nOUTPUT:\n", result)


        log_session(user_input, result)


if __name__ == "__main__":
    main()