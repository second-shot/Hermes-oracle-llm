from datetime import datetime, timedelta

from oracle_v1.contracts import ConfirmationRequest, NextAction, OracleEvent, OracleHeatLevel
from oracle_v1.state import resolve_oracle_state


def iso(minutes_ago: int = 0) -> str:
    return (datetime.utcnow() - timedelta(minutes=minutes_ago)).isoformat(timespec="seconds") + "Z"


def test_state_prefers_waiting_confirmation_over_recent_activity():
    state = resolve_oracle_state(
        events=[
            OracleEvent(
                id="evt-1",
                kind="oracle.intake.received",
                summary="Architect intake received",
                created_at=iso(3),
                mode="architect",
                risk_level="medium",
                metadata={},
            ),
            OracleEvent(
                id="evt-2",
                kind="oracle.task.requested",
                summary="Task execution requested",
                created_at=iso(1),
                mode="architect",
                risk_level="high",
                metadata={},
            ),
        ],
        confirmations=[
            ConfirmationRequest(
                id="conf-1",
                event_id="evt-2",
                action_label="Execute risky task",
                reason="High-risk task keywords detected",
                risk_level="high",
                status="pending",
                created_at=iso(1),
                decided_at=None,
            )
        ],
        next_action=NextAction(
            id="act-1",
            kind="await_confirmation",
            title="Review the confirmation",
            summary="Approve or reject the risky action before execution.",
            requires_confirmation=True,
            metadata={},
        ),
    )

    assert state.visual_state == "waiting_confirmation"
    assert state.heat_level == OracleHeatLevel.PASTEL_CONFIRM
    assert state.requires_confirmation is True
    assert state.last_event_summary == "Task execution requested"
    assert state.next_best_action.title == "Review the confirmation"


def test_state_reports_success_after_completed_event_without_pending_confirmation():
    state = resolve_oracle_state(
        events=[
            OracleEvent(
                id="evt-3",
                kind="oracle.task.completed",
                summary="Task executed safely",
                created_at=iso(0),
                mode="classic",
                risk_level="low",
                metadata={},
            )
        ],
        confirmations=[],
        next_action=NextAction(
            id="act-2",
            kind="continue",
            title="Keep momentum",
            summary="Submit the next request when ready.",
            requires_confirmation=False,
            metadata={},
        ),
    )

    assert state.visual_state == "success"
    assert state.heat_level == OracleHeatLevel.LIQUID_GOLD_SUCCESS
    assert state.requires_confirmation is False
    assert state.urgency == "low"
