# Execution Plan

What was built to take ARIA from a keyword-routing skeleton to a fully
implemented, tested, documented agent framework — and how each item was verified.

## Starting point

The skeleton had a working single-tool agent loop with: keyword-only routing, an
approval gate that always returned `True`, in-memory-list memory, an `eval()`
calculator, a stub Celery task, and one health-endpoint test. Cost/trace modules
existed but were trivial.

## Work delivered

### Tools (4+ real, hardened)
- **calculator** — replaced `eval()` with an `ast`-based whitelist evaluator
  (`safe_eval`); rejects names/calls/attributes; caps exponents.
- **file_reader** — sandboxed to `ARIA_SANDBOX_DIR` with `Path.is_relative_to`
  containment; rejects `..` traversal and absolute paths.
- **web_search** — deterministic mock offline; real HTTP via
  `shared_core.clients.BaseHTTPClient` when `ARIA_SEARCH_API_URL` is set.
- **task_creator** — persists a task via the active store (`make_task_creator`).
- **email_draft** — returns a structured draft, `sent: false`; never sends.
- **ToolRegistry** — added `Permission` levels and `build_default_registry`.

### Routing (sim/real)
- `routing.py` — `KeywordRouter` + `LLMRouter`. The LLM router simulates
  deterministically by default and uses `AgentLLMClient` → `LLMClientFactory`
  when keyed; it validates tool names against the registry and falls back to
  keyword routing on any failure.
- `llm_client.py` — offline-first LLM wrapper mirroring the monitor's SDK.

### Approval queue (real)
- `store.py` / `store_db.py` — in-memory and DB approval stores with an identical
  `pending → approved/rejected/expired` lifecycle and timeout.
- `approvals.py` — `ApprovalGate.evaluate()` creates pending approvals in
  `approval_gated` mode; legacy boolean API retained.

### Persistence (DB default + fallback)
- `models.py` — `AgentRun`, `MemoryMessage`, `ApprovalRecord`, `CreatedTask`.
- `db.py` — 2s connect-timeout probe selecting DB vs in-memory stores.
- `memory.py` — `PersistentMemory` alongside `AgentMemory`, chosen by `get_memory`.
- `alembic/` — env + initial migration for all four tables.

### Cost + tracing
- `costs.py` — `CostTracker` over `shared_core.llmmetrics`.
- `tracing.py` — `TraceLog` emitting `shared_core.tracing.Span` trees (run + per
  decision + per tool call), AgentTrace-compatible.

### API
- `main.py` — `POST /agent/chat`, `GET /agent/runs`, `GET /agent/runs/{id}`,
  `GET /agent/trace/{id}`, `GET /approvals`, `GET /approvals/{id}`,
  `POST /approvals/{id}/approve`, `POST /approvals/{id}/reject`, `GET /tools`,
  `GET /tools/{name}`, `GET /health`.

### Worker
- `worker.py` — real `aria.run_agent` and `aria.sweep_expired_approvals`
  tasks; importable with no broker.

### Examples
- Rewrote `examples/run_demo.py` (full end-to-end with assertions) and added
  `research_agent.py`, `task_agent.py`, `approval_gated_agent.py`.

### Tests (152, all offline)
- `test_tools.py`, `test_routing.py`, `test_agents.py`, `test_approvals.py`,
  `test_memory.py`, `test_costs_tracing.py`, `test_stores.py`, `test_worker.py`,
  `test_api.py`, plus `conftest.py` using `shared_core.testing` mocks.
- Golden cases: calculator arithmetic, cost == `shared_core.pricing`, routing
  decisions, approval lifecycle on both backends, sandbox traversal safety.

### Spine + docs
- Updated `pyproject.toml`, `requirements.txt`, `Makefile`, `.env.example`,
  `pytest.ini`, `docker-compose.yml`, `Dockerfile`.
- Rewrote `README.md` (with Mermaid architecture) and all `docs/*.md`; added this
  plan; updated `AGENTS.md`.

## Verification

| Step | Result |
|------|--------|
| `ruff format` + `ruff check src/aria tests examples` | Clean |
| `pytest -q` | 152 passed |
| `python examples/run_demo.py` | Exit 0 (assertions pass) |
| `research_agent` / `task_agent` / `approval_gated_agent` | Exit 0 |
| `alembic upgrade head` (SQLite) | Creates all 4 tables |
| DB-backed run survives a simulated restart | Verified (runs/tasks/approvals persist) |

## Remaining gaps (documented, not blocking)

- Single-step loop (no multi-hop chaining yet).
- No dedicated prompt-injection classifier (structural defenses only).
- Approval expiry is lazy/sweep, not a live timer.
- No API auth (showcase).
