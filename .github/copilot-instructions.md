# HERMES GODMODE 1000X — Copilot Instructions

You are working inside Hermes Oracle LLM.

Hermes is a local-first AI operating system for MAXI. Its purpose is to turn chaos into executable structure: capture inputs, compress context, classify intent, score priority, route to the right process, execute safely, validate output, store memory, and create Git checkpoints.

CORE RULES:
- Prefer simple working code over clever fragile code.
- Keep runtime cost near zero by default.
- Do not add paid APIs unless explicitly requested.
- Do not add network calls unless needed and clearly justified.
- Do not use sudo/admin/system-level changes.
- Do not delete user data.
- Keep all generated files inside the repository unless instructed otherwise.
- Before large changes, inspect existing files first.
- After any working change, recommend: test → git status → commit → push.

ARCHITECTURE INTENT:
- ORACLE = planning, compression, routing, memory, decision layer.
- MIA = tactical executor, closes loops, chooses the next viable action.
- OPERATOR = resale/value/task operating layer.
- Hermes = runtime shell tying agents, memory, tools, local models, and Git checkpoints together.

BUILD STYLE:
- Python-first unless repo proves otherwise.
- Local-first.
- Deterministic routing before LLM calls.
- Config-driven behaviour.
- Minimal dependencies.
- Small modules.
- Clear command names.
- Every function should have one job.
- Every agent action should be logged.

COST CONTROL:
- Default mode: local/offline.
- Cloud fallback must be optional, disabled by default, and controlled by config.
- Never hardcode paid keys.
- Never assume unlimited API usage.
- Add budget guards where cloud/model calls exist.

VALIDATION:
- Run the smallest relevant test first.
- If no tests exist, add a minimal smoke test.
- Check syntax before committing.
- Do not claim success unless commands actually pass.

OUTPUT STYLE FOR MAXI:
- Direct.
- Copy-paste ready.
- No fluff.
- One strongest next action.
- Always mention when to commit and push.
