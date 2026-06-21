import json
import threading
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from oracle_v1.http_api import build_server


def request_json(url: str, method: str = "GET", payload: dict | None = None) -> tuple[int, dict]:
    body = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers=headers, method=method)
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        return error.code, json.loads(error.read().decode("utf-8"))


def test_oracle_http_flow_creates_events_confirmations_and_observability(tmp_path):
    server = build_server("127.0.0.1", 0, data_root=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        base_url = f"http://127.0.0.1:{server.server_port}"

        status_code, health = request_json(f"{base_url}/api/health")
        assert status_code == 200
        assert health["status"] == "ok"
        assert health["data"]["service"] == "oracle-v1"

        status_code, intake = request_json(
            f"{base_url}/api/oracle/intake",
            method="POST",
            payload={
                "mode": "architect",
                "text": "Delete the old production logs and deploy the new plan",
                "objective": "Turn this chaos into a safe execution plan",
                "metadata": {"source": "test"},
            },
        )
        assert status_code == 200
        assert intake["status"] == "ok"
        assert intake["data"]["event"]["kind"] == "oracle.intake.received"
        assert intake["data"]["requiresConfirmation"] is True
        confirmation_id = intake["data"]["confirmation"]["id"]

        status_code, confirmations = request_json(f"{base_url}/api/confirmations")
        assert status_code == 200
        assert confirmations["data"]["items"][0]["id"] == confirmation_id

        status_code, approved = request_json(
            f"{base_url}/api/confirmations/{confirmation_id}/approve",
            method="POST",
            payload={"decisionNote": "Safe in test mode"},
        )
        assert status_code == 200
        assert approved["data"]["confirmation"]["status"] == "approved"
        assert approved["data"]["state"]["requiresConfirmation"] is False

        status_code, state = request_json(f"{base_url}/api/oracle/state")
        assert status_code == 200
        assert state["data"]["visualState"] in {"active", "success"}

        status_code, events = request_json(f"{base_url}/api/oracle/events")
        assert status_code == 200
        assert len(events["data"]["items"]) >= 2

        status_code, notifications = request_json(f"{base_url}/api/notifications")
        assert status_code == 200
        assert any(item["kind"] == "confirmation.approved" for item in notifications["data"]["items"])

        status_code, memory = request_json(f"{base_url}/api/memory")
        assert status_code == 200
        assert "oracle_v1" in memory["data"]["structured"]

        status_code, logs = request_json(f"{base_url}/api/logs")
        assert status_code == 200
        assert any("confirmation.approved" in entry["message"] for entry in logs["data"]["entries"])
    finally:
        server.shutdown()
        server.server_close()


def test_safe_task_execution_returns_execution_without_confirmation(tmp_path):
    server = build_server("127.0.0.1", 0, data_root=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        status_code, execution = request_json(
            f"{base_url}/api/tasks/execute",
            method="POST",
            payload={
                "mode": "architect",
                "task": "Summarize the current local operator status",
                "metadata": {"source": "test"},
            },
        )
        assert status_code == 200
        assert execution["status"] == "ok"
        assert execution["data"]["requiresConfirmation"] is False
        assert execution["data"]["execution"]["mode"] == "stub"
        assert execution["data"]["state"]["visualState"] == "success"
    finally:
        server.shutdown()
        server.server_close()


def test_confirmation_cannot_be_approved_twice(tmp_path):
    server = build_server("127.0.0.1", 0, data_root=tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        status_code, execution = request_json(
            f"{base_url}/api/tasks/execute",
            method="POST",
            payload={
                "mode": "architect",
                "task": "Deploy the updated production release",
                "metadata": {"source": "test"},
            },
        )
        assert status_code == 200
        assert execution["data"]["requiresConfirmation"] is True
        confirmation_id = execution["data"]["confirmation"]["id"]

        status_code, first_approval = request_json(
            f"{base_url}/api/confirmations/{confirmation_id}/approve",
            method="POST",
            payload={"decisionNote": "Proceed once"},
        )
        assert status_code == 200
        assert first_approval["data"]["confirmation"]["status"] == "approved"

        status_code, second_approval = request_json(
            f"{base_url}/api/confirmations/{confirmation_id}/approve",
            method="POST",
            payload={"decisionNote": "Proceed again"},
        )
        assert status_code == 200
        assert second_approval["status"] == "error"
        assert second_approval["error"]["code"] == "invalid_confirmation_state"

        status_code, events = request_json(f"{base_url}/api/oracle/events")
        assert status_code == 200
        completed_events = [item for item in events["data"]["items"] if item["kind"] == "oracle.task.completed"]
        assert len(completed_events) == 1
    finally:
        server.shutdown()
        server.server_close()
