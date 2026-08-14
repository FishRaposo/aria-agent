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
| dashboard | existing Next.js read-only portfolio surface |

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

`RunEvent` has a monotonic sequence, a stable type (`reasoning`, `decision`,
`approval`, `tool`, `error`, or `complete`), and a JSON payload. The synchronous
path and `/agent/chat/stream` use the same engine event sink. Replay reads the
recorded tool entries and returns a `ReplayResult`; dry-run is default and never
executes side effects.

## Persistence and optional services

Runs, approvals, tasks, and memory use the existing SQLAlchemy schema when the
database probe succeeds. Otherwise the in-memory stores provide the same public
methods. Redis, Celery, and PostgreSQL are optional operational integrations;
the package, demo, and CI do not need them to be running.

## Provenance

The server-used compatibility subset is vendored under
`src/aria/internal/vendor_core/` and pinned in `THIRD_PARTY_NOTICES.md`. No
runtime import resolves to a sibling checkout or an external Git URL.
