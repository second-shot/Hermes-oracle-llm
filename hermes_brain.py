from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from typing import Any

from memory.store import append_context_event, read_context_profile, update_memory


RESALE_KEYWORDS = (
    "resale",
    "inventory",
    "listing",
    "list on",
    "price",
    "value",
    "valuation",
    "vinted",
    "ebay",
    "depop",
    "facebook marketplace",
    "profit",
    "sold",
    "offer",
    "sell",
    "item",
    "photo",
    "photos",
)
LISTING_DRAFT_KEYWORDS = (
    "listing draft",
    "draft listing",
    "generate listing",
    "create listing",
    "write listing",
    "describe item for sale",
    "listing description",
    "listing template",
)
MEMORY_KEYWORDS = ("remember", "memory", "recall", "archive", "summarise", "summarize", "compress")
REPO_KEYWORDS = ("repo", "code", "debug", "bug", "patch", "test", "commit", "branch")
PLANNING_KEYWORDS = ("plan", "route", "strategy", "design", "architecture", "brain")
ACTION_KEYWORDS = ("publish", "post", "send", "buy", "pay", "approval", "approve")
FREEBUFF_KEYWORDS = ("freebuff", "logarhythm", "subangel repair", "fridge brain")


@dataclass(frozen=True)
class BrainDecision:
    request: str
    normalized_request: str
    task_type: str
    specialist: str
    route: str
    complexity_score: int
    needs_approval: bool
    missing_information: list[str]
    next_step: str
    context: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "normalized_request": self.normalized_request,
            "task_type": self.task_type,
            "specialist": self.specialist,
            "route": self.route,
            "complexity_score": self.complexity_score,
            "needs_approval": self.needs_approval,
            "missing_information": self.missing_information,
            "next_step": self.next_step,
            "context": self.context,
        }


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text)).strip()


def _contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in text for keyword in keywords)


def classify_task(text: str, metadata: dict[str, Any] | None = None) -> str:
    lower = normalize_text(text).lower()
    metadata = metadata or {}
    if metadata.get("freebuff_bridge") or _contains_any(lower, FREEBUFF_KEYWORDS):
        return "freebuff_bridge"
    if metadata.get("listing_draft") or _contains_any(lower, LISTING_DRAFT_KEYWORDS):
        return "listing_draft"
    if metadata.get("inventory") or metadata.get("resale") or _contains_any(lower, RESALE_KEYWORDS):
        return "resale"
    if _contains_any(lower, MEMORY_KEYWORDS):
        return "memory"
    if _contains_any(lower, REPO_KEYWORDS):
        return "repo"
    if _contains_any(lower, PLANNING_KEYWORDS):
        return "planning"
    return "general"


def score_complexity(text: str, metadata: dict[str, Any] | None = None) -> int:
    lower = normalize_text(text).lower()
    metadata = metadata or {}
    score = 10 + min(len(lower) // 20, 40)
    if any(token in lower for token in ("compare", "research", "evaluate", "estimate", "value", "pricing")):
        score += 10
    if any(token in lower for token in ("photo", "image", "picture", "inventory")):
        score += 8
    if len(re.findall(r"\d+", lower)) >= 2:
        score += 6
    if metadata.get("photos"):
        score += 6
    if metadata.get("condition") or metadata.get("brand") or metadata.get("size"):
        score += 4
    return max(0, min(score, 100))


def _resale_missing_information(text: str, metadata: dict[str, Any]) -> list[str]:
    lower = text.lower()
    missing: list[str] = []
    for key in ("condition", "brand", "size"):
        if not metadata.get(key) and key not in lower:
            missing.append(key)
    if not metadata.get("photos") and "photo" not in lower and "image" not in lower:
        missing.append("photos")
    return missing


def route_specialist(task_type: str, text: str) -> str:
    if task_type == "freebuff_bridge":
        return "LOGARHYTHM BRIDGE"
    if task_type == "resale":
        return "RESALE AGENT"
    if task_type == "listing_draft":
        return "LISTING DRAFTER"
    if task_type == "memory":
        return "MEMORY KEEPER"
    if task_type == "repo":
        return "REPO AGENT"
    if task_type == "planning":
        return "TASK PLANNER"
    return "GENERAL ASSISTANT"


def next_step_for(specialist: str, missing_information: list[str]) -> str:
    if specialist == "LOGARHYTHM BRIDGE":
        return (
            "Read the reviewed Freebuff export or connected repository through the read-only bridge; "
            "import approved LOGARHYTHM UI, assets, and rules while keeping private Fridge Brain memory local."
        )
    if specialist == "RESALE AGENT":
        if missing_information:
            return "Collect the missing item details, then generate the listing draft."
        return "Produce the listing draft, price band, and approval request."
    if specialist == "LISTING DRAFTER":
        if missing_information:
            return "Collect the missing item details, then generate the listing draft text."
        return "Produce the listing draft text, title, and description for approval."
    if specialist == "MEMORY KEEPER":
        return "Summarise the durable memory and update the archive."
    if specialist == "REPO AGENT":
        return "Inspect the repository context and choose the smallest safe fix."
    return "Return the smallest safe next action."


class HermesBrain:
    def __init__(self, *, memory_namespace: str = "hermes_brain") -> None:
        self.memory_namespace = memory_namespace

    def intake(self, text: str, metadata: dict[str, Any] | None = None) -> BrainDecision:
        metadata = metadata or {}
        normalized = normalize_text(text)
        task_type = classify_task(normalized, metadata)
        specialist = route_specialist(task_type, normalized)
        missing_information = (
            _resale_missing_information(normalized, metadata)
            if specialist in {"RESALE AGENT", "LISTING DRAFTER"}
            else []
        )
        needs_approval = bool(
            specialist == "LOGARHYTHM BRIDGE"
            or (
            specialist in {"RESALE AGENT", "LISTING DRAFTER"}
            and (
                missing_information
                or _contains_any(normalized.lower(), ACTION_KEYWORDS)
                or metadata.get("needs_approval", True)
            )
            )
        )
        decision = BrainDecision(
            request=str(text),
            normalized_request=normalized,
            task_type=task_type,
            specialist=specialist,
            route=task_type,
            complexity_score=score_complexity(normalized, metadata),
            needs_approval=needs_approval,
            missing_information=missing_information,
            next_step=next_step_for(specialist, missing_information),
            context=read_context_profile(self.memory_namespace),
        )
        append_context_event(
            self.memory_namespace,
            {
                "event": "intake",
                "task_type": decision.task_type,
                "specialist": decision.specialist,
                "complexity_score": decision.complexity_score,
                "needs_approval": decision.needs_approval,
                "missing_information": decision.missing_information,
            },
        )
        return decision

    def record_outcome(self, decision: BrainDecision, outcome: dict[str, Any]) -> None:
        update_memory({"task_type": decision.task_type}, {"result": outcome})
        append_context_event(
            self.memory_namespace,
            {
                "event": "outcome",
                "task_type": decision.task_type,
                "specialist": decision.specialist,
                "result": outcome,
            },
        )

    def analyse(self, text: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.intake(text, metadata).to_dict()

    def route(self, text: str, metadata: dict[str, Any] | None = None) -> str:
        return self.intake(text, metadata).specialist


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Mia deterministic brain router")
    sub = parser.add_subparsers(dest="command", required=True)
    route = sub.add_parser("route")
    route.add_argument("text")
    route.add_argument("--metadata", default="{}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    brain = HermesBrain()
    metadata = json.loads(args.metadata)
    if not isinstance(metadata, dict):
        metadata = {}
    if args.command == "route":
        print(json.dumps(brain.analyse(args.text, metadata), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
