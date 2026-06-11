import json
from datetime import datetime


STRUCTURED_PATH = "memory/structured.json"
LOG_PATH = "memory/logs.md"


def read_memory(prompt):
    try:
        with open(STRUCTURED_PATH, "r") as f:
            return json.load(f)
    except:
        return {}


def update_memory(prompt, response):
    try:
        data = read_memory(prompt)
    except:
        data = {}


    key = prompt["task_type"]
    data[key] = response


    with open(STRUCTURED_PATH, "w") as f:
        json.dump(data, f, indent=2)


def log_session(user_input, output):
    with open(LOG_PATH, "a") as f:
        f.write(f"\n[{datetime.now()}]\n")
        f.write(f"INPUT: {user_input}\n")
        f.write(f"OUTPUT: {output}\n")