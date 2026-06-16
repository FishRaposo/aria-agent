# Failure Modes & Mitigations

How Hermes behaves when dependencies misbehave, and how failures are contained.
The framework is built to **degrade, not crash**: every external effect has a
fallback and every tool returns a string rather than propagating an exception to
the caller.

## Dependency failures

| Failure | Symptom | Mitigation |
|---------|---------|------------|
| Database unreachable | Startup probe times out (≤ `DB_PROBE_TIMEOUT`, default 2s) | `db.check_db()` logs a warning and selects in-memory stores; service runs normally without persistence |
| DB driver not installed | `ImportError` on probe | Same fallback path — `db.py` imports the driver lazily, so the module still imports |
| Redis / broker down | Worker can't dispatch | API is unaffected (no Redis dependency on the request path); `worker.py` still imports with no broker |
| OpenAI/Anthropic unreachable or no key | Real LLM call fails | `AgentLLMClient` catches it, records the error in telemetry, and returns a mock response; routing degrades to keyword |
| Web search endpoint down | `web_search` HTTP error | Caught; falls back to the deterministic mock knowledge base |

## Tool-level failures

| Failure | Behaviour |
|---------|-----------|
| Unknown tool routed | `_execute_tool` catches `KeyError`, traces an error span, returns `"Error: Tool '<x>' not available."` (status `error`) |
| Invalid tool arguments | `ToolRegistry.call_tool` raises `pydantic.ValidationError` before the tool runs; the agent surfaces it as a structured error span |
| Calculator injection payload | AST walk raises `ValueError`; `calculator` returns `"Error evaluating expression: ..."` — no code executes |
| Calculator division by zero / huge exponent | Returned as an error string, not an exception |
| File path traversal / outside sandbox | `file_reader` returns `"Error: access denied ..."`; never reads outside the sandbox |
| File not UTF-8 / missing | Returned as a descriptive error string |

## Approval-queue edge cases

| Case | Behaviour |
|------|-----------|
| Approval times out before decision | Status transitions `pending → expired` (lazily on read, or via the sweep task); approve/reject become no-ops returning the expired record |
| Approve an already-approved/rejected approval | API returns `409 Conflict`; store `decide()` is idempotent (keeps the first decision) |
| Approve/reject an unknown id | API returns `404 Not Found` |
| Risky tool in free-running mode | Executes directly (no pause) — by design; gating is a per-request/mode choice |

## API error contract

- `404` — unknown run, approval, or tool.
- `409` — deciding an approval that is no longer pending.
- `BaseApplicationError` subclasses are rendered as structured JSON by
  `shared_core.errors.application_error_handler`.

## Resource bounds

| Risk | Bound |
|------|-------|
| Unbounded memory growth | `AgentMemory`/`PersistentMemory` apply a sliding window (`max_messages`, default 50) on read |
| Runaway exponentiation | Calculator caps the `pow` exponent (1000) |
| Oversized file reads | `file_reader` truncates to a byte cap (4000 chars) |
| Oversized tool results in traces | Trace entries truncate result strings to 500 chars |

## What is *not* mitigated (known gaps)

- **No retries on tool execution** — a transient tool failure is returned as an
  error for the run; retry/backoff is on the roadmap.
- **No background expiry timer** — approval timeouts are realized on read or by
  the periodic sweep task, not by a live timer.
- **No auth / rate limiting on the API** — out of scope for a showcase.
