import subprocess
import sys

COMMANDS = [
    ["status"],
    ["character"],
    ["security"],
    ["rights"],
    ["skills"],
    ["sources"],
    ["ethical-check", "status check"],
    ["source-plan", "build local bridge"],
    ["security-check", "build local bridge"],
    ["decide", "build local bridge"],
    ["tick", "status check"],
    ["validate"],
]


def test_hermes_employee_cli_v2_commands():
    for args in COMMANDS:
        result = subprocess.run([sys.executable, "hermes_employee.py", *args], capture_output=True, text=True)
        assert result.returncode == 0, f"{args} failed: {result.stderr}\n{result.stdout}"
