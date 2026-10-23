# Architecture

ARIA keeps the execution core small and inspectable. Every route, approval,
tool call, persistence write, cost record, and trace event is explicit.

## Layers

| Layer | Responsibility |
|---|---|
| `internal/core` | `AgentEngine`, bounded plans, run events, safety, retry, rate limits, replay, local vector index |
| compatibility facades | `aria.agents`, `routing`, `tools`, `approvals`, `memory`, `costs`, and `tracing` preserve public behavior |
| `internal/vendor_core` | pinned local configuration, database, errors, health, logging, pricing, client, task, testing, and tracing primitives |
| API | FastAPI chat, SSE stream, runs, replay, memory search, approvals, tools, and health endpoints |
| stores | SQLAlchemy/PostgreSQL when reachable; identical in-memory interfaces offline |
| dashboard | Next.js walkthrough, explicit sample/connected providers, tab-local shared scenario state |

## Execution flow

```text
query -> safety assessment -> bounded plan -> route decision(s)
      -> rate limit -> approval gate -> validated tool call -> trace/cost
      -> memory + run store -> ordered completion event
```

`planning_mode=single` preserves the original one-tool behavior. `multi` splits
explicit `then`/`;` steps and truncates them at `AGENT_MAX_STEPS`. A blocked
safety assessment ends the run before routing. Retry policies are injectable and
default to one attempt with no delay. The fixed-window limiter is keyed by
session and tool and is disabled by default.

## Events, streaming, and replay

In the strict gated/block profile, schema/tool/workspace checks also run at
dispatch. Approval decisions and execution claims are separate. Each approval
binds a copied action, arguments, run and expiry; one lock/CAS transition commits
the claim before a tool can execute. SQL claim metadata survives restart. A
crash may leave an uncertain `claimed` outcome; there is no automatic retry.
See [the case study](portfolio-case-study.md) for tradeoffs and measured evidence.

`RunEvent` has a monotonic sequence, a stable type (`reasoning`, `decision`,
`approval`, `tool`, `error`, or `complete`), and a JSON payload. The synchronous
path and `/agent/chat/stream` use the same engine event sink. Replay reads the
recorded tool entries and returns a `ReplayResult`; dry-run is default and never
executes side effects.

Even the current non-dry replay path is recorded playback, not tool re-execution.
The `replayed` flag does not mean an external effect occurred; the result exposes
`side_effects_executed=false`.

## Persistence and optional services

Runs, approvals, tasks, and memory use the existing SQLAlchemy schema when the
database probe succeeds. Otherwise the in-memory stores provide the same public
methods. Redis, Celery, and PostgreSQL are optional operational integrations;
the package, demo, and CI do not need them to be running.

## Provenance

The server-used compatibility subset is vendored under
`src/aria/internal/vendor_core/` and pinned in `THIRD_PARTY_NOTICES.md`. No
runtime import resolves to a sibling checkout or an external Git URL.

## Connected application evidence (2026-10-23)

The API creates a separate automatic skill session per run. Canonical shipped
skills live in `.agents/skills`, become wheel resources at build time, and never
inherit ambient home/project trust. Saved runs carry nullable session identity,
skill snapshots and approval origin. Read models project authoritative approval
results/traces and durably deduplicate final conversation outcomes without tool
redispatch. The frontend selects a session, inspects a saved run, and resets only
leaf view state when switching context. See the [connected architecture and
recovery contract](portfolio-connected.md) for interfaces, migration and limits.
