from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from core.executor import execute_task

from .adapters import LocalAuthAdapter, LocalStorageAdapter, NoopRealtimeAdapter
from .contracts import ArchitectIntent, ConfirmationRequest, NextAction, Notification, OracleEvent
from .intents import detect_architect_intent, detect_risk_level, make_next_action, normalize_text
from .responses import error, ok
from .state import resolve_oracle_state


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


class OracleService:
    def __init__(self, data_root: Path):
        self.storage = LocalStorageAdapter(data_root)
        self.auth = LocalAuthAdapter()
        self.realtime = NoopRealtimeAdapter()
        self.store = self.storage.get_store()

    @classmethod
    def from_repo_root(cls) -> "OracleService":
        return cls(Path(__file__).resolve().parent.parent)

    def health(self) -> dict:
        return ok({"service": "oracle-v1", "mode": "local-first", "operator": self.auth.current_operator()})

    def list_events(self) -> dict:
        return ok({"items": self.store.read_events()})

    def list_confirmations(self) -> dict:
        return ok({"items": self.store.read_confirmations()})

    def list_notifications(self) -> dict:
        return ok({"items": self.store.read_notifications()})

    def get_memory(self) -> dict:
        return ok({"structured": self.store.read_structured_memory()})

    def get_logs(self) -> dict:
        raw = (self.store.memory_root / "logs.md").read_text(encoding="utf-8")
        return ok({"entries": self.store.read_activity_log(), "raw": raw})

    def get_state(self) -> dict:
        state = resolve_oracle_state(
            events=self._event_objects(),
            confirmations=self._confirmation_objects(),
            next_action=self._default_next_action(),
        )
        return ok(state.to_dict())

    def submit_intake(self, payload: dict) -> dict:
        mode = str(payload.get("mode") or "architect")
        text = str(payload.get("text") or "").strip()
        objective = str(payload.get("objective") or "").strip()
        task = str(payload.get("task") or "").strip()
        metadata = payload.get("metadata") or {}
        upload_payload = payload.get("upload") or None

        if not normalize_text(text, objective, task):
            return error("invalid_intake", "At least one of text, objective, or task is required.")

        risk_level = detect_risk_level(normalize_text(text, objective, task))
        architect_intent = detect_architect_intent(mode, text, objective, task)

        event = OracleEvent(
            id=f"evt-{uuid4().hex[:12]}",
            kind="oracle.intake.received",
            summary="Architect intake received" if mode == "architect" else "Classic chat intake received",
            created_at=utc_now(),
            mode=mode,
            risk_level=risk_level,
            metadata={
                "text": text,
                "objective": objective,
                "task": task,
                "metadata": metadata,
                "upload": upload_payload,
                "architectIntent": architect_intent.to_dict() if architect_intent else None,
            },
        )
        self._append_event(event)

        confirmation = None
        if risk_level in {"medium", "high"}:
            confirmation = ConfirmationRequest(
                id=f"conf-{uuid4().hex[:12]}",
                event_id=event.id,
                action_label="Review risky intake",
                reason="Risk keywords detected in the intake payload.",
                risk_level=risk_level,
                status="pending",
                created_at=utc_now(),
                decided_at=None,
                metadata={"source": "intake", "text": text, "objective": objective, "task": task},
            )
            self._append_confirmation(confirmation)
            self._append_event(
                OracleEvent(
                    id=f"evt-{uuid4().hex[:12]}",
                    kind="oracle.confirmation.requested",
                    summary="Confirmation required for intake",
                    created_at=utc_now(),
                    mode=mode,
                    risk_level=risk_level,
                    metadata={"confirmationId": confirmation.id, "relatedEventId": event.id},
                )
            )
            self._notify("confirmation.requested", "Confirmation needed", "Risky intake needs review before the next step.", "warning", confirmation_id=confirmation.id)
            next_action = make_next_action(
                "await_confirmation",
                "Review the confirmation",
                "Approve or reject the risky intake before continuing.",
                True,
                confirmationId=confirmation.id,
            )
        else:
            next_action = make_next_action(
                "plan_route",
                "Review the suggested route",
                "Confirm the objective and choose whether to execute a safe next step.",
                False,
            )
            self._notify("intake.recorded", "Intake captured", "A new Oracle event was recorded.", "info", event_id=event.id)

        state = resolve_oracle_state(self._event_objects(), self._confirmation_objects(), next_action)
        return ok(
            {
                "event": event.to_dict(),
                "architectIntent": architect_intent.to_dict() if architect_intent else None,
                "nextAction": next_action.to_dict(),
                "requiresConfirmation": confirmation is not None,
                "confirmation": confirmation.to_dict() if confirmation else None,
                "state": state.to_dict(),
            }
        )

    def request_task_execution(self, payload: dict) -> dict:
        mode = str(payload.get("mode") or "architect")
        text = str(payload.get("text") or payload.get("task") or payload.get("objective") or "").strip()
        metadata = payload.get("metadata") or {}

        if not text:
            return error("invalid_task", "Task execution requires a text or task field.")

        risk_level = detect_risk_level(text)
        requested_event = OracleEvent(
            id=f"evt-{uuid4().hex[:12]}",
            kind="oracle.task.requested",
            summary="Task execution requested",
            created_at=utc_now(),
            mode=mode,
            risk_level=risk_level,
            metadata={"text": text, "metadata": metadata},
        )
        self._append_event(requested_event)

        if risk_level in {"medium", "high"}:
            confirmation = ConfirmationRequest(
                id=f"conf-{uuid4().hex[:12]}",
                event_id=requested_event.id,
                action_label="Execute requested task",
                reason="Task execution matches a risky keyword and needs explicit approval.",
                risk_level=risk_level,
                status="pending",
                created_at=utc_now(),
                decided_at=None,
                metadata={"source": "task_execute", "text": text, "mode": mode},
            )
            self._append_confirmation(confirmation)
            self._append_event(
                OracleEvent(
                    id=f"evt-{uuid4().hex[:12]}",
                    kind="oracle.confirmation.requested",
                    summary="Confirmation required for task execution",
                    created_at=utc_now(),
                    mode=mode,
                    risk_level=risk_level,
                    metadata={"confirmationId": confirmation.id, "relatedEventId": requested_event.id},
                )
            )
            self._notify("confirmation.requested", "Task blocked pending confirmation", "Approve or reject the task execution request.", "warning", confirmation_id=confirmation.id)
            next_action = make_next_action("await_confirmation", "Review the task confirmation", "Approval is required before execution.", True, confirmationId=confirmation.id)
            state = resolve_oracle_state(self._event_objects(), self._confirmation_objects(), next_action)
            return ok(
                {
                    "event": requested_event.to_dict(),
                    "execution": None,
                    "nextAction": next_action.to_dict(),
                    "requiresConfirmation": True,
                    "confirmation": confirmation.to_dict(),
                    "state": state.to_dict(),
                }
            )

        execution = self._run_safe_execution(text)
        completed_event = OracleEvent(
            id=f"evt-{uuid4().hex[:12]}",
            kind="oracle.task.completed",
            summary="Task executed safely",
            created_at=utc_now(),
            mode=mode,
            risk_level=risk_level,
            metadata={"requestedEventId": requested_event.id, "execution": execution},
        )
        self._append_event(completed_event)
        self._notify("task.executed", "Task executed", "A safe local execution completed.", "success", event_id=completed_event.id)
        next_action = make_next_action("continue", "Review execution output", "Inspect the result and decide the next step.", False, eventId=completed_event.id)
        state = resolve_oracle_state(self._event_objects(), self._confirmation_objects(), next_action)
        return ok(
            {
                "event": completed_event.to_dict(),
                "execution": execution,
                "nextAction": next_action.to_dict(),
                "requiresConfirmation": False,
                "confirmation": None,
                "state": state.to_dict(),
            }
        )

    def approve_confirmation(self, confirmation_id: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        confirmations = self.store.read_confirmations()
        target = next((item for item in confirmations if item["id"] == confirmation_id), None)
        if target is None:
            return error("not_found", f"Confirmation '{confirmation_id}' was not found.")
        if target.get("status") != "pending":
            return error(
                "invalid_confirmation_state",
                f"Confirmation '{confirmation_id}' is already {target.get('status')}.",
                {"confirmationId": confirmation_id, "status": target.get("status")},
            )

        target["status"] = "approved"
        target["decided_at"] = utc_now()
        target.setdefault("metadata", {})["decisionNote"] = payload.get("decisionNote", "")
        self.store.write_confirmations(confirmations)

        source = target.get("metadata", {}).get("source")
        execution = None
        if source == "task_execute":
            execution = self._run_safe_execution(str(target.get("metadata", {}).get("text") or ""))
            self._append_event(
                OracleEvent(
                    id=f"evt-{uuid4().hex[:12]}",
                    kind="oracle.task.completed",
                    summary="Approved task executed safely",
                    created_at=utc_now(),
                    mode=str(target.get("metadata", {}).get("mode") or "architect"),
                    risk_level=str(target.get("risk_level") or "medium"),
                    metadata={"confirmationId": confirmation_id, "execution": execution},
                )
            )

        approval_event = OracleEvent(
            id=f"evt-{uuid4().hex[:12]}",
            kind="oracle.confirmation.approved",
            summary="Confirmation approved",
            created_at=utc_now(),
            mode="architect",
            risk_level=str(target.get("risk_level") or "medium"),
            metadata={"confirmationId": confirmation_id, "execution": execution},
        )
        self._append_event(approval_event)
        self._notify("confirmation.approved", "Confirmation approved", "The operator approved the pending action.", "success", confirmation_id=confirmation_id)
        next_action = make_next_action("continue", "Continue with the approved flow", "The pending action was approved. Review the updated state and next step.", False, confirmationId=confirmation_id)
        state = resolve_oracle_state(self._event_objects(), self._confirmation_objects(), next_action)
        return ok(
            {
                "confirmation": target,
                "execution": execution,
                "state": state.to_dict(),
                "nextAction": next_action.to_dict(),
            }
        )

    def reject_confirmation(self, confirmation_id: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        confirmations = self.store.read_confirmations()
        target = next((item for item in confirmations if item["id"] == confirmation_id), None)
        if target is None:
            return error("not_found", f"Confirmation '{confirmation_id}' was not found.")
        if target.get("status") != "pending":
            return error(
                "invalid_confirmation_state",
                f"Confirmation '{confirmation_id}' is already {target.get('status')}.",
                {"confirmationId": confirmation_id, "status": target.get("status")},
            )

        target["status"] = "rejected"
        target["decided_at"] = utc_now()
        target.setdefault("metadata", {})["decisionNote"] = payload.get("decisionNote", "")
        self.store.write_confirmations(confirmations)

        self._append_event(
            OracleEvent(
                id=f"evt-{uuid4().hex[:12]}",
                kind="oracle.confirmation.rejected",
                summary="Confirmation rejected",
                created_at=utc_now(),
                mode="architect",
                risk_level=str(target.get("risk_level") or "medium"),
                metadata={"confirmationId": confirmation_id},
            )
        )
        self._notify("confirmation.rejected", "Confirmation rejected", "The operator rejected the pending action.", "info", confirmation_id=confirmation_id)
        next_action = make_next_action("stabilize", "Capture a safer next step", "The risky action was rejected. Rewrite the request or choose a safer action.", False, confirmationId=confirmation_id)
        state = resolve_oracle_state(self._event_objects(), self._confirmation_objects(), next_action)
        return ok(
            {
                "confirmation": target,
                "state": state.to_dict(),
                "nextAction": next_action.to_dict(),
            }
        )

    def _append_event(self, event: OracleEvent) -> None:
        items = self.store.read_events()
        items.append(event.to_dict())
        self.store.write_events(items)
        self._remember(event.kind, event.summary, {"event": event.to_dict()})
        self._log(event.kind, event.summary)

    def _append_confirmation(self, confirmation: ConfirmationRequest) -> None:
        items = self.store.read_confirmations()
        items.append(confirmation.to_dict())
        self.store.write_confirmations(items)
        self._remember("confirmation", confirmation.action_label, {"confirmation": confirmation.to_dict()})

    def _notify(self, kind: str, title: str, message: str, level: str, **metadata: str) -> None:
        notification = Notification(
            id=f"note-{uuid4().hex[:12]}",
            kind=kind,
            title=title,
            message=message,
            level=level,
            created_at=utc_now(),
            metadata=metadata,
        )
        items = self.store.read_notifications()
        items.append(notification.to_dict())
        self.store.write_notifications(items)
        self._remember(kind, message, {"notification": notification.to_dict()})
        self._log(kind, message)

    def _remember(self, kind: str, summary: str, payload: dict) -> None:
        structured = self.store.read_structured_memory()
        oracle_memory = structured.setdefault("oracle_v1", {"entries": []})
        oracle_memory["entries"].append({"timestamp": utc_now(), "kind": kind, "summary": summary, "payload": payload})
        structured["oracle_v1"] = oracle_memory
        self.store.write_structured_memory(structured)

    def _log(self, kind: str, message: str) -> None:
        items = self.store.read_activity_log()
        entry = {"timestamp": utc_now(), "kind": kind, "message": f"{kind}: {message}"}
        items.append(entry)
        self.store.write_activity_log(items)
        self.store.append_markdown_log(kind, message)

    def _event_objects(self) -> list[OracleEvent]:
        return [OracleEvent(**item) for item in self.store.read_events()]

    def _confirmation_objects(self) -> list[ConfirmationRequest]:
        return [ConfirmationRequest(**item) for item in self.store.read_confirmations()]

    def _default_next_action(self) -> NextAction:
        pending = any(item.status == "pending" for item in self._confirmation_objects())
        if pending:
            return make_next_action("await_confirmation", "Review pending confirmation", "Approve or reject the pending action.", True)
        return make_next_action("continue", "Submit the next action", "Create a new intake or execute a safe task.", False)

    def _run_safe_execution(self, text: str) -> dict:
        config_path = Path(__file__).resolve().parent.parent / "config.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["cloud_enabled"] = False
        config.setdefault("llm", {})["provider"] = "stub"
        result = execute_task(text, config)
        return {"mode": "stub", "result": result}
