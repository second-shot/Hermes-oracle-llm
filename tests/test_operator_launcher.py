import sys

from scripts import operator
from memory.store import read_context_profile


def test_local_model_alias_is_kept_when_it_points_to_fast_model() -> None:
    loaded = [
        {
            "identifier": "hermes-free",
            "modelKey": "qwen3-1.7b",
            "path": "lmstudio-community/Qwen3-1.7B-GGUF/Qwen3-1.7B-Q4_K_M.gguf",
        }
    ]

    assert operator.model_needs_reload(loaded) is False


def test_local_model_alias_is_reloaded_when_it_points_to_slow_model() -> None:
    loaded = [
        {
            "identifier": "hermes-free",
            "modelKey": "qwen3.5-4b-verified",
            "path": "qwen3.5-4b-verified",
        }
    ]

    assert operator.model_needs_reload(loaded) is True


def test_freebuff_command_targets_the_hermes_project(tmp_path) -> None:
    executable = tmp_path / "freebuff.cmd"
    project_root = tmp_path / "Hermes-oracle-llm"

    command = operator.freebuff_command(executable=executable, project_root=project_root)

    assert command == [str(executable), "--cwd", str(project_root)]


def test_launch_freebuff_hands_the_hermes_project_to_the_cli(tmp_path) -> None:
    executable = tmp_path / "freebuff.cmd"
    project_root = tmp_path / "Hermes-oracle-llm"
    observed = {}

    def run(command, *, cwd):
        observed["command"] = command
        observed["cwd"] = cwd
        return 0

    exit_code = operator.launch_freebuff(
        executable=executable,
        project_root=project_root,
        run=run,
    )

    assert exit_code == 0
    assert observed == {
        "command": [str(executable), "--cwd", str(project_root)],
        "cwd": str(project_root),
    }


def test_freebuff_mode_does_not_start_the_local_model(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["operator.py", "--freebuff"])
    monkeypatch.setattr(operator, "launch_freebuff", lambda: 0)

    def fail_if_called():
        raise AssertionError("LM Studio must not start for the Freebuff bridge")

    monkeypatch.setattr(operator, "prepare_model", fail_if_called)

    assert operator.main() == 0


def test_operator_task_routes_executes_records_and_returns_next_action(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HERMES_DATA_DIR", str(tmp_path / "runtime"))

    def local_inference(prompt, config):
        assert "resale_agents.health" in prompt
        assert '"inventory_count": 0' in prompt
        assert "Mia verified next action: Capture one item with title, condition, and photos." in prompt
        assert config["cloud_enabled"] is False
        return {
            "result": "Your resale inventory is empty. Capture one item with title, condition, and photos.",
            "cache": "miss",
        }

    result = operator.execute_operator_task(
        "Check resale inventory status and tell me the next action.",
        {"cloud_enabled": False},
        model_execute=local_inference,
    )

    assert result["route"] == "resale"
    assert result["specialist"] == "RESALE AGENT"
    assert result["action"] == "resale_agents.health"
    assert result["action_result"]["inventory_count"] == 0
    assert "Capture one item" in result["result"]
    assert result["next_action"] == "Capture one item with title, condition, and photos."

    profile = read_context_profile("hermes_brain")
    outcome = profile["last_event"]
    assert outcome["event"] == "outcome"
    assert outcome["result"]["action"] == "resale_agents.health"
    assert outcome["result"]["action_result"]["inventory_count"] == "0"


def test_operator_status_routes_pending_approval_to_review(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HERMES_DATA_DIR", str(tmp_path / "runtime"))

    class FakeService:
        def health(self):
            return {
                "status": "ok",
                "service": "resale-agents",
                "mode": "local-only",
                "inventory_count": 2,
                "pending_approvals": 1,
                "latest_item_id": "item-2",
            }

    result = operator.execute_operator_task(
        "Check resale inventory status and tell me the next action.",
        {"cloud_enabled": False},
        model_execute=lambda *_args: {"result": "Review the pending approval.", "cache": "miss"},
        resale_service=FakeService(),
    )

    assert result["action"] == "resale_agents.health"
    assert result["next_action"] == "Review the 1 pending resale approval before generating more drafts."


def test_operator_status_routes_populated_inventory_to_latest_item(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HERMES_DATA_DIR", str(tmp_path / "runtime"))

    class FakeService:
        def health(self):
            return {
                "status": "ok",
                "service": "resale-agents",
                "mode": "local-only",
                "inventory_count": 2,
                "pending_approvals": 0,
                "latest_item_id": "item-2",
            }

    result = operator.execute_operator_task(
        "Check resale inventory health and tell me the next action.",
        {"cloud_enabled": False},
        model_execute=lambda *_args: {"result": "Open item-2.", "cache": "miss"},
        resale_service=FakeService(),
    )

    assert result["next_action"] == "Open item-2 and generate its listing draft for approval."


def test_listing_draft_request_is_not_replaced_by_inventory_status(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("HERMES_DATA_DIR", str(tmp_path / "runtime"))

    def local_inference(prompt, _config):
        assert "resale_agents.health" not in prompt
        return {"result": "Provide the item details for the draft.", "cache": "miss"}

    result = operator.execute_operator_task(
        "Create a listing draft for my vintage watch.",
        {"cloud_enabled": False},
        model_execute=local_inference,
    )

    assert result["specialist"] == "LISTING DRAFTER"
    assert result["action"] is None
    assert result["action_result"] is None
