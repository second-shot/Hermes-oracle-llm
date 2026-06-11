1. SYSTEM_OVERVIEW
- architecture_type: Hybrid local-first with optional cloud escalation
- core_design_philosophy: Deterministic routing, minimal model calls, local execution preferred, cost and call minimization, M1-optimized local LLM with structured semantic compression and caching

2. ROUTING_RULES
- IF task_type == "vision" AND cloud_enabled == true THEN use_cloud
- ELSE IF task_type in ["text_reasoning", "coding", "automation", "memory", "retrieval"] THEN
  attempt_local(max_attempts=2)
  IF local_fails_after_2_attempts AND cloud_configured AND cloud_enabled THEN use_cloud
  ELSE IF local_fails_after_2_attempts AND (NOT cloud_configured OR NOT cloud_enabled) THEN return_error
- ELSE use_local

3. TASK_CLASSIFIER
- categories: ["vision", "text_reasoning", "coding", "automation", "memory", "retrieval"]
- mapping_rules:
  * vision: IF input_has_image_reference THEN vision
  * coding: ELSE IF input_has_code_keywords THEN coding
  * automation: ELSE IF input_has_automation_keywords THEN automation
  * memory: ELSE IF input_is_memory_storage_recall THEN memory
  * retrieval: ELSE IF input_is_information_search THEN retrieval
  * ELSE: text_reasoning

4. PROMPT_COMPRESSOR_SPEC
- remove_rules:
  * excess_whitespace: collapse multiple spaces to one, trim
  * filler_words: remove ["very", "really", "quite", "actually", "basically", "simply", "please", "could you", "would you"] when not critical
  * polite_phrases: remove ["please", "could you", "would you mind", "thank you"] at start/end
  * repeated_phrases: remove consecutive duplicate phrases
  * semantic_redundancy: remove non-essential adjectives/adverbs, collapse intent to verb-object core
- keep_rules:
  * key_entities: capitalized terms, numbers, proper nouns
  * constraints: explicit modifiers (fast, cheap, local, cloud, secure, minimal)
  * core_instruction: main action verb and object
- output_schema: structured packet with task_type, goal, entities, constraints, and compressed_prompt string
- compression_technique: converts natural language to ultra-compact execution packet format:
  T:<task_type>
  G:<goal>
  E:<comma-separated entities>
  C:<comma-separated constraints>

5. MEMORY_SYSTEM
- structure:
  * ~/.hermes/memory/user_facts.json
  * ~/.hermes/memory/session_logs/ (timestamped files)
  * ~/.hermes/memory/knowledge_base/ (text files)
- stored:
  * user_facts: key-value pairs (JSON)
  * session_logs: compressed session summaries
  * knowledge_base: user notes, procedures, facts
- ignored:
  * raw chat logs, temporary context, verbose logs
- retrieval_rules:
  * user_facts: exact key match
  * session_logs & knowledge_base: case-insensitive keyword search (OR of keywords) returning top 3 most recent files with snippets

6. MODEL_USAGE_POLICY
- primary_model: Local GGUF model (Llama-3-8B-Instruct-Q4_K_M) via llama.cpp
- fallback_rules:
  * non_vision: local_attempts=2 -> cloud_attempt=1 (if configured and cloud_enabled)
  * vision: cloud_attempts=2 (if configured and cloud_enabled)
- strict_constraints:
  * n_ctx: 2048
  * n_threads: 4 (M1 optimized)
  * n_batch: 128
  * temperature: 0.2 (deterministic)
  * stop_token: ["\n"]
  * max_output_tokens: dynamically set by task type (see COST_CONTROL_SYSTEM)
  * cloud_enabled: false by default

7. AUTOMATION_LAYER
- allowed automation types:
  * shell_scripts: in ~/hermes/automation/, no sudo, no network calls without approval
  * applescript: pre-approved app control (open, quit, basic actions)
  * file_ops: read/write/move/delete in ~/hermes/ and user's documents (if allowed)
- restrictions:
  * no system file modification
  * no package installation without approval
  * no external network calls from automation (use agent's cloud tool for approved APIs)
- execution_boundaries:
  * each automation runs in isolated shell process
  * full logging of commands and outputs

8. FAILURE_HANDLING
- retry_logic:
  * local: max_retries=2, backoff=1s
  * cloud: max_retries=1
- fallback_logic:
  * non_vision: local_fail_after_2 -> cloud (if configured, cloud_enabled, and under daily limit)
  * vision: cloud_fail_after_1 -> retry_cloud (if under daily limit) then fail
- invalid_output_handling:
  * if expected_format not met, attempt to extract valid output (e.g., find JSON in text) else return error

9. COST_CONTROL_SYSTEM
- token_minimization_rules:
  * always apply prompt_compressor_v2 (structured semantic compression)
  * max_output_tokens per task type:
     text_reasoning: 100
     coding: 200
     automation: 50
     memory: 50
     retrieval: 50
     vision: 150
- call_limits:
  * local: unlimited (subject to hardware constraints)
  * cloud:
     daily_non_vision_fallback: 5
     daily_vision: 10
- caching_layer:
  * exact_cache: identical compressed prompts -> reuse response
  * semantic_cache: similar T/G/E/C packets (threshold=0.85) -> reuse response
  * storage: ~/.hermes/cache/exact.json and ~/.hermes/cache/semantic.json
- batching_strategy: none (per-task processing)

10. FINAL_ARCHITECTURE_SPEC
- A hybrid system that prioritizes local execution on a quantized GGUF Llama 3 8B model (Q4_K_M) running via llama.cpp, optimized for M1 MacBook with 8GB RAM.
- Features a deterministic semantic compressor (v2) that reduces input tokens by 40-70% by converting natural language into structured execution packets (T:task_type, G:goal, E:entities, C:constraints).
- Implements a two-layer cache system (exact and semantic) between the compressor and LLM call to prevent duplicate inference and reduce costs by an additional 20-50%.
- Vision tasks and fallback for failed local attempts use a single configured cloud API only when explicitly enabled via cloud_enabled=true.
- Deterministic routing based on task classification (rule-based) minimizes complexity and ensures predictable behavior.
- Memory is stored in a lightweight file-based system with keyword retrieval for user facts, session logs, and knowledge base.
- Automation is restricted to safe, user-approved operations within the user's directory and Hermes workspace.
- Cost is controlled via prompt compression (v2), token limits per task type, strict daily cloud call limits (when enabled), and caching layer.
- Failure handling includes limited retries and defined fallbacks to minimize unnecessary cloud usage and ensure system stability.
- The system operates at zero runtime cost when cloud is disabled, relying solely on the efficient local LLM with advanced compression and caching.