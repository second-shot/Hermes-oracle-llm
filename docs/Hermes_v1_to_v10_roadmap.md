# Hermes V1–V10 Research Roadmap

## V1 – Hermes Kernel
- Create stable core: Memory, Projects, Router, Oracle, Downloads, Skills, Persistence.
- Audit existing files and move dead/experimental code to `archive/`.
- Commit message: feat(kernel): hermes kernel stable.

## V2 – Memory Spine
- Design Working, Short Term, Long Term, Archive, Identity and Project memory modules.
- Implement `compression_engine.py` to compress Raw → Summary → Insight → Principle.
- Persist memory in JSON; ensure retrieval across sessions.
- Commit: feat(memory): implement Hermes memory spine with compression.

## V3 – Research Spine
- Collect signals from GitHub, Papers, arXiv, Reddit, X/Twitter, YouTube, Google Trends, forums, news and docs.
- Classify signals by domain and score on novelty, velocity, relevance, money potential, evidence strength, actionability and risk.
- Verify claims through documentation and local tests.
- Generate daily reports and watchlists.
- Commit: feat(research): add research spine with signal, scoring and verification.

## V4 – Model Orchestrator & Registry
- Download Qwen3 4B MLX, Qwen2.5‑Coder 3B and SmolVLM‑500M models; store in `models/`.
- Create `mlx_runtime.py` for MLX; keep fallback runtime for llama.cpp.
- Create `model_registry.json` mapping reasoning, coding and vision models to these defaults.
- Commit: feat(models): add MLX runtime and model registry for Qwen and SmolVLM.

## V5 – Downloads Brain
- Monitor the Downloads directory; classify files and route them to memory, research or resale modules.
- Extract metadata and perform OCR or image classification as needed.
- Commit: feat(downloads): implement intake pipeline with classification and routing.

## V6 – Operator (Resale Engine)
- Implement pricing engine for items based on research data; suggest platform, confidence and expected profit.
- Provide CLI interface for item valuation.
- Commit: feat(operator): add resale valuation engine and CLI integration.

## V7 – MIA (Execution Agent)
- Build deterministic agent for follow‑ups, message generation, organisation and scheduling without LLM inference.
- Enforce strict automation boundaries per SPEC.md.
- Commit: feat(mia): add deterministic execution agent.

## V8 – Oracle (Meta‑Cognition)
- Build prioritisation engine scanning memory, research and goals to answer “What matters now?”
- Return top 3 priorities via CLI.
- Commit: feat(oracle): add meta-cognition prioritisation module.

## V9 – Hermes Swarm
- Define roles for Archivist, Scout, Trader, Watchman and Engineer agents, sharing the same memory spine.
- Implement a lightweight message bus for agent communication.
- Commit: feat(swarm): implement specialised agents and shared memory.

## V10 – Hermes OS
- Integrate all modules into a cohesive CLI; add optional TUI/dashboard for status and reports.
- Update documentation (README.md, docs/ARCHITECTURE.md, docs/MODEL_SETUP.md, docs/CHANGELOG.md).
- Commit: docs: update documentation for Hermes OS.
