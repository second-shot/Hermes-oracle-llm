# Architecture Decision Records

## ADR-001: Local-first runtime

Decision: MIA runs locally by default with no hidden network/cloud calls.

Reason: The operator must be inspectable, free to run, and not dependent on Copilot credits or paid APIs.

Consequence: External research and cloud actions require explicit future design and approval.

## ADR-002: JSON state for MVP

Decision: Use small JSON files for tasks, approvals, heartbeat, scoreboards, sources, and policies.

Reason: JSON is easy to inspect, version, repair, and understand.

Consequence: Add schemas and validator early. Consider SQLite only after state volume grows.

## ADR-003: Approval gates over autonomy

Decision: Medium/high risk work creates proposals instead of silent execution.

Reason: The runtime must remain safe, reversible, and auditable.

Consequence: Some tasks will feel slower, but trust and control improve.

## ADR-004: Defensive security only

Decision: Security mode supports owned/local/lab defensive work and refuses harmful/offensive requests.

Reason: Strong security capability must not become abuse capability.

Consequence: Red-team style thinking is allowed only to protect owned systems and produce safe mitigations.

## ADR-005: Standard library MVP

Decision: The MVP uses Python standard library only.

Reason: Fewer install failures, less dependency risk, no network installs required.

Consequence: Advanced testing/dashboard features are deferred or implemented as optional extras.
