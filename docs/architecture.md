# Architecture

ARIA is a controlled agent framework. The design goal is a **small, auditable
core** where every external effect (tool call, LLM call, persistence write) is
explicit, validated, traced, and cost-accounted. This document describes the
components, the data model, and the offline-first execution model.

## Component map

| Module | Responsibility |
|--------|----------------|
| `main.py` | FastAPI gateway; wires stores + agent; exposes the REST surface |
| `agents.py` | `AriaAgent` — the reason/route/approve/act loop; returns a `RunResult` |
| `routing.py` | `KeywordRouter` (deterministic) + `LLMRouter` (sim/real) → `RouteDecision` |
| `llm_client.py` | `AgentLLMClient` — offline-first LLM wrapper (mock short-circuit, real when keyed) |
| `tools.py` | `ToolRegistry` with `Permission` levels; `build_default_registry()` |
| `builtin_tools/` | The five real tools (calculator, web_search, file_reader, task_creator, email_draft) |
| `approvals.py` | `ApprovalGate` — bridges risky tool calls to the approval queue |
| `memory.py` | `AgentMemory` (in-memory) + `PersistentMemory` (DB) behind `get_memory()` |
| `store.py` / `store_db.py` | Run / task / approval stores: in-memory + SQLAlchemy backends |
| `db.py` | DB-availability probe + store selection |
| `models.py` | SQLAlchemy ORM models (`AgentRun`, `MemoryMessage`, `ApprovalRecord`, `CreatedTask`) |
| `costs.py` | `CostTracker` over `shared_core.llmmetrics` |
| `tracing.py` | `TraceLog` producing `shared_core.tracing.Span` trees |
| `worker.py` | Celery app with real agent + approval-sweep tasks |
| `config.py` | `AppConfig` extending `shared_core.config.BaseAppConfig` |

## The agent loop

`AriaAgent.run_structured(query)` performs one pass:

```
add query to memory
  → route(query)                       # LLMRouter (sim/real) or KeywordRouter
      → RouteDecision(tool, arguments, strategy)
  → if no tool: generate a direct response, finish
  → permission = registry.requires_approval(tool)
  → gate.evaluate(tool, args, requires_approval, mode)
      → approved   → call_tool(tool, args)   # schema-validated, traced, costed
      → pending    → create approval, pause, return approval id
  → store result in memory
  → finish → RunResult(status, route, approval, trace, cost)
```

Two public entrypoints share this body:

- `run(query) -> str` — backward-compatible string reply (used by the demo and
  the original tests).
- `run_structured(query) -> RunResult` — the full structured result used by the API.

`execute_approved(action, arguments)` runs a tool that was approved out-of-band
(via `POST /approvals/{id}/approve`), reusing the same `_execute_tool` path so
tracing is consistent.

## Routing

Routing is pluggable via `build_router(strategy, llm_client)`:

- **`KeywordRouter`** — deterministic regex/keyword matching. Always available,
  no keys, no network. Order matters: arithmetic → email → task → search → file,
  so ambiguous phrases like *"create a task to file the report"* route to
  `task_creator` (task intent) rather than `file_reader`.
- **`LLMRouter`** — formats a routing prompt and asks an LLM for a JSON decision.
  Following the offline-first / real-when-keyed pattern, a `mocked_response`
  (derived deterministically from the keyword router) short-circuits the call;
  with keys set, the real provider runs via `AgentLLMClient` → `LLMClientFactory`.
  The router **validates the chosen tool name** against the registry and rejects
  hallucinated tools, falling back to keyword routing. Every LLM call is recorded
  in the run's `CostTracker`.

## Permissions and the approval queue

Each tool carries a `Permission`:

- `SAFE` — read-only/compute (`calculator`, `web_search`, `file_reader`). Runs directly.
- `REQUIRES_APPROVAL` — produces a side effect or artifact (`task_creator` writes
  a row; `email_draft` produces an outbound message). Gated.

The `ApprovalGate` has two modes:

- **`free_running`** — risky tools execute directly (still logged for audit).
- **`approval_gated`** — risky tools create a **pending approval** and the run
  pauses. The approval lifecycle is `pending → approved | rejected | expired`,
  with a configurable timeout. Expiry is evaluated lazily on read (and can be
  swept by the Celery `sweep_expired_approvals` task). Both the in-memory and
  DB-backed stores enforce the identical lifecycle (shared `ApprovalStatus` and
  expiry rule), and a decision on an already-decided/expired approval is a no-op.

## Persistence model

```
agent_runs(id, query, response, mode, status, route, trace_json, cost_json, ts)
memory_messages(id, session_id, role, content, seq, ts)
approvals(id, run_id, action, parameters_json, status, reason, expires_at, decided_at, ts)
created_tasks(id, title, description, status, ts)
```

All models extend `shared_core.database` `Base` + `UUIDMixin` + `TimestampMixin`.
Schema is managed by Alembic (`alembic/versions/0001_initial_schema.py`).

### DB-availability probe

On startup `db.check_db()` opens one connection with a short connect timeout
(`DB_PROBE_TIMEOUT`, default 2s). If the database is reachable it calls
`create_tables()` and sets `db_available = True`; the `build_*_store()` helpers
then return the SQLAlchemy-backed stores and `get_memory()` returns
`PersistentMemory`. If the database is unreachable — or its driver is absent,
the offline-first default for tests and the demo — every builder transparently
returns the in-memory store. The probe uses a throwaway engine, so importing
`db.py` never requires a Postgres driver.

This is why **the entire test suite and demo run with no database**: the probe
fails fast and the code paths are identical apart from the store implementation.

## Cost and tracing

- **Cost** — `CostTracker` wraps `shared_core.llmmetrics.LLMMetrics`, whose cost
  defaults to `shared_core.pricing.calculate_cost`. This keeps token pricing and
  latency percentiles identical to the rest of the portfolio. The run's cost
  summary includes totals, per-model cost, and p50/p95/p99 latency.
- **Tracing** — `TraceLog` creates a root `agent.run` span plus one child span
  per decision (`SpanType.DECISION`) and per tool call (`SpanType.TOOL`), all
  sharing one `trace_id`. Spans are `shared_core.tracing.Span` instances, so the
  serialized trace is AgentTrace-compatible and can be POSTed to a collector via
  `shared_core.tracing.emit_span`.

## Async worker

`worker.py` builds a Celery app via `shared_core.tasks.create_celery_app`. It is
importable with **no broker running** (the broker is only contacted when a worker
starts or a task is dispatched). Tasks:

- `aria.run_agent` — run the agent on a query and persist the run.
- `aria.sweep_expired_approvals` — materialise approval timeouts.

Both have pure helper functions (`_run_agent`, `_sweep_expired_approvals`) so
they're unit-testable without Celery.

## Offline-first contract

Every external dependency degrades gracefully:

| Dependency | Absent behaviour |
|------------|------------------|
| Database | In-memory stores (probe fallback) |
| Redis / broker | Worker importable; API unaffected |
| OpenAI/Anthropic keys | Simulated routing + responses |
| Web search endpoint | Deterministic mock knowledge base |
| `sentence-transformers`/`torch` | Never imported — not a dependency |
