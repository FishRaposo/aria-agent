# Aria Agent — Architecture (v0.3)

> Cross-provider model router with cooperation patterns **AND a v0.1 tool agent preserved**. v0.3 unifies both into a single orchestrator. Tool-friendly queries go to fast local tools (calculator, web_search, file_reader, task_creator, email_draft); everything else goes to the cross-provider router.

## System overview

A FastAPI service. The user sends a task via `POST /agent/run`. The gateway delegates to `AriaAgent`, which:

1. **Classifies intent** (IntentClassifier) — is this a tool-friendly query or a model-required query?
2. **Tool path:** If tool-friendly, delegate to `KeywordRouterAgent` (v0.1, preserved). The legacy agent does keyword matching, dispatches to the registered tool, returns the tool's output wrapped in a `CooperationResult`.
3. **Model path:** Otherwise, classify the task (`TaskClassifier` → `TaskType`), route to a (provider, model) triple (`ModelSelector` → `RoutingDecision`), and execute a cooperation pattern (`Cascade` | `PlanExecuteValidate` | `Ensemble`).
4. **Returns** a `CooperationResult` with the final output + full step transcript (uniform across both paths).

The agent and registry are constructed once at app startup and shared across requests. **No module-level mutable state per request** (the v0.1 codebase had this bug — fixed in v0.2, preserved in v0.3).

## Component map

| Layer | Module | Responsibility |
|---|---|---|
| **API Gateway** | `src/aria_agent/main.py` | FastAPI app, endpoint routing, dependency wiring |
| **Agent Core (v0.3)** | `src/aria_agent/agent.py` | `AriaAgent.run()` — intent classification + path dispatch |
| **Tool path (v0.1)** | `src/aria_agent/agents.py` | `KeywordRouterAgent` — keyword-routing tool agent (preserved) |
| **Tool registry (v0.1)** | `src/aria_agent/tools.py` + `builtin_tools/` | `ToolRegistry` + 5 builtin tools (calculator, web_search, file_reader, task_creator, email_draft) |
| **v0.1 components** | `approvals.py`, `memory.py`, `costs.py`, `tracing.py`, `worker.py` | Approval gate, conversation memory, cost tracking, trace log, Celery worker (all preserved) |
| **Cooperation Patterns (v0.2)** | `src/aria_agent/cooperation/` | 3 patterns that orchestrate multiple model calls |
| **Router (v0.2)** | `src/aria_agent/router/` | Classify task + pick best (provider, model) |
| **Providers (v0.2)** | `src/aria_agent/providers/` | 3 LLM providers (OCG, MiniMax, Codex) + base + registry |
| **Configuration** | `src/aria_agent/config.py` | Pydantic settings, env vars |

## Data flow: a single request

### Model path (the common case)

```
User: POST /agent/run {"task": "Translate to Portuguese", "pattern": "cascade"}
   ↓
FastAPI gateway (main.py)
   ↓ validates request
AriaAgent.run(task, pattern="cascade")
   ↓
classify_intent(task) → Intent.MODEL_CALL (no tool keyword matched)
   ↓
CascadePattern.execute(task, router, registry)
   ↓
router.select_for_task_description(task)
   ↓
   classifier.classify(task)        → TaskType.TRANSLATION
   router.find_by_task(TRANSLATION) → [kimi-k2.6, glm-5.1, ...]
   selector.select(...)             → RoutingDecision(primary=kimi-k2.6, fallback=mimo-v2.5)
   ↓
CascadePattern:
   1. cheap = mimo-v2.5 (cheap workhorse)
   2. Call mimo → assess_quality → if OK, return; else escalate
   3. best = kimi-k2.6 (escalation target)
   4. Call kimi-k2.6 → return its output
   ↓
CooperationResult {
   final_output: "Olá, mundo",
   pattern: "cascade",
   intent: "model_call",
   num_steps: 2,
   num_models_used: 2,
   total_cost_usd: 0.0054,
   steps: [mimo_step, kimi_step],
   metadata: {cascade_outcome: "escalated", ...}
}
   ↓
FastAPI gateway serializes → JSON response
```

### Tool path (the fast case)

```
User: POST /agent/run {"task": "calculate 7 * 6"}
   ↓
FastAPI gateway (main.py)
   ↓ validates request
AriaAgent.run(task)
   ↓
classify_intent("calculate 7 * 6")
   ↓
   matched keyword "calculate" + has digits → Intent.TOOL_CALL
   matched_tool = "calculator"
   ↓
AriaAgent._run_tool_path(task, classification)
   ↓
KeywordRouterAgent.run("calculate 7 * 6")
   ↓
   _plan_action → ("calculator", {"expression": "7 * 6"})
   ↓
   ApprovalGate.request_approval("calculator", {...}) → True
   ↓
   ToolRegistry.call_tool("calculator", {"expression": "7 * 6"})
   ↓
   eval("7 * 6", {"__builtins__": {}}, {}) → 42
   ↓
   "Result: 42"
   ↓
   TraceLog.add_tool_call(...)
   CostTracker.record_call(...)
   AgentMemory.add_message(...)
   ↓
CooperationResult {
   final_output: "Result: 42",
   pattern: "keyword_router",
   intent: "tool_call",
   num_steps: 1,
   num_models_used: 0,
   total_cost_usd: 0.0,
   total_latency_ms: <1ms,
   steps: [StepResult(step_name="keyword_router_tool_call", provider_name="keyword_router", ...)],
   metadata: {matched_tool: "calculator", matched_keyword: "calculate", v0_1_trace: {...}, v0_1_cost: {...}}
}
   ↓
FastAPI gateway serializes → JSON response (latency: <1ms, no LLM cost)
```

## Key design decisions

### 1. Two paths, one orchestrator (v0.3)

v0.3 unified the v0.1 tool agent and the v0.2 router into a single `AriaAgent`. The `AriaAgent.run()` flow:

1. `classify_intent(task)` → `Intent.TOOL_CALL` or `Intent.MODEL_CALL`
2. If `TOOL_CALL` → delegate to `KeywordRouterAgent` (the v0.1 reason-and-act loop). The result is wrapped in a `CooperationResult` so the API surface stays uniform.
3. If `MODEL_CALL` → use the `ModelSelector` + `CooperationPattern` (the v0.2 path).

The intent classifier is rule-based v1: match tool keywords (calculate/search/read/task/email), verify the tool is registered, check the calculator special case (no digits → still model path). LLM-based classifier is on the roadmap.

The keyword table is in `_TOOL_KEYWORDS` (in `agent.py`) and mirrored in `KeywordRouterAgent._plan_action` (in `agents.py`). They must stay in sync — when you add a tool, update both.

### 2. Provider is lazy

`ProviderRegistry` constructs a provider only when its key is set. Lets the agent run with partial key configuration (e.g., OCG-only if the user hasn't paid for MiniMax/Codex yet).

### 2. OCG's split routing is encoded in the provider

OCG serves 11+ models across 2 protocols (chat-completions for Kimi/MiniMax/mimo/Qwen 3.6, Anthropic Messages for Qwen 3.7). The router doesn't know about this — it just says "use kimi-k2.6", and the provider's `OPENCODE_GO_MODELS` table figures out the protocol.

If OCG adds a new model with a new protocol, only `opencode_go.py` needs to change.

### 3. Specialist > generalist in the routing table

For specialty tasks (REASONING, LONG_CONTEXT, VISION), specialists win (tier rank 0-2). For general tasks (CODING_DEFAULT, GENERAL, WRITING), M3 (generalist, DEFAULT tier) wins. The tier ordering is:
- BEST_QUALITY (rank 0) — Kimi K2.6, GLM-5.1
- LONG_CONTEXT (rank 1) — DeepSeek V4 Pro
- MULTIMODAL (rank 2) — Kimi K2.5
- LEGACY (rank 3)
- DEFAULT (rank 4) — MiniMax-M3
- CHEAP_WORKHORSE (rank 5) — mimo-v2.5
- PRO_PLUS (rank 6) — Claude/GPT (not in active pool, available on Pro+ plan)

### 4. Cooperation patterns return CooperationResult, not strings

The agent and gateway are designed around structured results. Every model call is recorded as a `StepResult` (model, input, output, latency, cost, success). The trace is auditable end-to-end.

### 5. No module-level mutable state per request

`main.py` constructs `agent`, `registry`, and `router` once at startup. They're shared across requests because they're stateless (registry has lazy construction; router is a pure data structure; agent holds pattern instances which are stateless too). This fixes the v0.1 bug where every request shared the same `AgentMemory` and `CostTracker`.

### 6. Per-pattern quality check

Cascade uses `assess_quality` (length + refusal detection) to decide whether to escalate. v1 is rule-based; v2 will use LLM-as-judge. The hook is in place.

## Failure modes

| Failure | Handling |
|---|---|
| Provider API key missing | Provider not constructed, `get()` raises `KeyError`. Cooperation patterns catch and return a degraded result with metadata. |
| Provider returns empty output | `assess_quality` marks as unacceptable → cascade escalates. Ensemble picks the longest non-empty output. |
| Provider rate-limited | `_call_model` returns a `StepResult` with `success=False, error=...`. Pattern decides whether to retry or surface. |
| Escalation target's provider not registered | `cascade.py` catches `KeyError` and returns the cheap output with `cascade_outcome: "escalation_failed_returned_cheap"` + the intended escalation in metadata. |
| Validator rejects the executor's output | `plan_execute.py` retries up to `max_retries` times with the validator's feedback. After max retries, returns the best step by quality score. |
| All models fail | CooperationResult with `final_output: "(no output produced)"` and a step transcript of all failures. Agent returns 500. |

## See also

- `README.md` — user-facing docs, quick start
- `AGENTS.md` — agent-facing docs (orientation, source module table, conventions)
- `examples/run_demo.py` — runnable live demo
