from __future__ import annotations

from .contracts import ConfirmationRequest, NextAction, OracleEvent, OracleHeatLevel, OracleState
from .intents import make_next_action


def resolve_oracle_state(
    events: list[OracleEvent],
    confirmations: list[ConfirmationRequest],
    next_action: NextAction | None = None,
) -> OracleState:
    pending_confirmations = [item for item in confirmations if item.status == "pending"]
    last_event = events[-1] if events else None
    last_summary = last_event.summary if last_event else "Oracle idle and waiting."

    if pending_confirmations:
        action = next_action or make_next_action(
            "await_confirmation",
            "Review pending confirmation",
            "Approve or reject the pending action before the system continues.",
            True,
        )
        urgency = "high" if any(item.risk_level == "high" for item in pending_confirmations) else "medium"
        return OracleState(
            visual_state="waiting_confirmation",
            heat_level=OracleHeatLevel.PASTEL_CONFIRM,
            urgency=urgency,
            requires_confirmation=True,
            next_best_action=action,
            last_event_summary=last_summary,
        )

    if not events:
        action = next_action or make_next_action(
            "idle",
            "Submit a new request",
            "Use Classic Chat or Architect intake to create the next Oracle event.",
            False,
        )
        return OracleState(
            visual_state="idle",
            heat_level=OracleHeatLevel.COLD_CONTROL,
            urgency="low",
            requires_confirmation=False,
            next_best_action=action,
            last_event_summary=last_summary,
        )

    if last_event.kind.endswith(".completed") or last_event.kind.endswith(".approved"):
        action = next_action or make_next_action(
            "continue",
            "Keep momentum",
            "Review the result and submit the next useful action.",
            False,
        )
        return OracleState(
            visual_state="success",
            heat_level=OracleHeatLevel.LIQUID_GOLD_SUCCESS,
            urgency="low",
            requires_confirmation=False,
            next_best_action=action,
            last_event_summary=last_summary,
        )

    if last_event.risk_level == "high":
        action = next_action or make_next_action(
            "stabilize",
            "Reduce urgency",
            "Clarify the risky action before proceeding.",
            False,
        )
        return OracleState(
            visual_state="urgent",
            heat_level=OracleHeatLevel.BURNING_URGENT,
            urgency="high",
            requires_confirmation=False,
            next_best_action=action,
            last_event_summary=last_summary,
        )

    action = next_action or make_next_action(
        "continue",
        "Continue the flow",
        "Capture the next action or execute a safe task.",
        False,
    )
    return OracleState(
        visual_state="active",
        heat_level=OracleHeatLevel.WARM_ACTIVE,
        urgency="medium",
        requires_confirmation=False,
        next_best_action=action,
        last_event_summary=last_summary,
    )

