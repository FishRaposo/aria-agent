# Roadmap

## Shipped

### Phase 1 — Tool framework
- [x] `ToolRegistry` with decorator + imperative registration
- [x] Pydantic schema validation before execution
- [x] `Permission` levels (`safe` / `requires_approval`)
- [x] Five real builtin tools (calculator, web_search, file_reader, task_creator, email_draft)
- [x] AST-safe calculator (no `eval`); sandboxed, traversal-safe file_reader

### Phase 2 — Agent intelligence + control
- [x] `KeywordRouter` (deterministic) and `LLMRouter` (sim/real with keyword fallback)
- [x] Real approval queue: pending → approved/rejected/expired with timeout
- [x] Free-running vs approval-gated modes
- [x] Persistent memory (DB) with in-memory fallback
- [x] Cost tracking via `shared_core.pricing` + `shared_core.llmmetrics`
- [x] AgentTrace-compatible span tree via `shared_core.tracing`

### Phase 3 — Platform
- [x] Full REST surface (chat, runs, runs/{id}, trace, approvals + approve/reject, tools, health)
- [x] DB-default persistence with startup probe + in-memory fallback
- [x] SQLAlchemy models + Alembic migrations
- [x] Celery worker with real tasks (`run_agent`, `sweep_expired_approvals`)
- [x] Three example agents (research, task, approval-gated)
- [x] 152 offline tests; ruff-clean; runnable demo

## Planned

### Phase 4 — Robustness & safety
- [ ] Multi-hop planning loop (chain several tool calls per run, using `max_steps`)
- [ ] Prompt-injection / content classifier over query and RAG context
- [ ] Per-tool retry/backoff policies
- [ ] Per-tool rate limits via `shared_core.ratelimit`

### Phase 5 — Experience & ops
- [ ] Streaming responses (SSE) from `/agent/chat`
- [ ] Approval webhooks / notifications instead of polling
- [ ] Run replay from persisted traces
- [ ] Background timer for approval expiry (not just lazy/sweep)
- [ ] Vector-backed long-term memory via `shared_core.vectorstore`

## Non-goals

- A bundled frontend — a later portfolio stage handles UIs. The API exposes
  everything a dashboard needs.
- A general tool marketplace — the registry is intentionally small and auditable.
