from __future__ import annotations

from typing import Any

from .contracts import ArchitectIntent, NextAction


HIGH_RISK_KEYWORDS = {
    "delete",
    "remove",
    "deploy",
    "production",
    "publish",
    "send",
    "email",
    "transfer",
    "key",
    "token",
    "password",
}

MEDIUM_RISK_KEYWORDS = {
    "edit",
    "modify",
    "rename",
    "move",
    "install",
    "execute",
    "run",
}

ARCHITECT_KEYWORDS = {
    "plan",
    "architect",
    "design",
    "build",
    "refactor",
    "debug",
    "objective",
    "roadmap",
}


def normalize_text(*parts: Any) -> str:
    return " ".join(str(part or "").strip() for part in parts if str(part or "").strip()).strip()


def detect_risk_level(text: str) -> str:
    lowered = text.lower()
    if any(keyword in lowered for keyword in HIGH_RISK_KEYWORDS):
        return "high"
    if any(keyword in lowered for keyword in MEDIUM_RISK_KEYWORDS):
        return "medium"
    return "low"


def detect_architect_intent(mode: str, text: str, objective: str, task: str) -> ArchitectIntent | None:
    combined = normalize_text(text, objective, task)
    lowered = combined.lower()
    if mode == "architect" or any(keyword in lowered for keyword in ARCHITECT_KEYWORDS):
        objective_text = objective or task or text or "Clarify the operator goal"
        confidence = 0.82 if mode == "architect" else 0.68
        rationale = "Architect mode or planning keywords indicate a plan-and-route request."
        return ArchitectIntent(
            id="intent-architect",
            label="software_architecture",
            confidence=confidence,
            rationale=rationale,
            objective=objective_text,
            metadata={"sourceText": combined},
        )
    return None


def make_next_action(kind: str, title: str, summary: str, requires_confirmation: bool, **metadata: Any) -> NextAction:
    return NextAction(
        id=f"action-{kind}",
        kind=kind,
        title=title,
        summary=summary,
        requires_confirmation=requires_confirmation,
        metadata=metadata,
    )

