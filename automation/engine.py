def run_command(cmd):
    allowed = ["ls", "echo", "cat"]


    base = cmd.split(" ")[0]


    if base not in allowed:
        return {"error": "blocked_command"}


    import os
    return os.popen(cmd).read()