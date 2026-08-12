# AGENTS.md — aria-agent-framework

## What This Is

ARIA is a controlled AI agent framework: a schema-validated tool registry with
permission levels, dual routing (deterministic keyword + LLM with sim/real),
a real human-in-the-loop approval queue, persistent memory, cost tracking, and
AgentTrace-compatible execution tracing. It is **offline-first**: the demo and
test suite are designed for no database, Redis, or API keys, using deterministic
simulation; real OpenAI/Anthropic and PostgreSQL paths activate when configured.

## Commands

```bash
make install     # pip install -e "../shared-core[dev,docparse]" numpy && pip install -e ".[dev]"
make dev         # uvicorn aria.main:app --reload --app-dir src (:8000)
make test        # pytest -q (full suite; shared_core must be installed)
make lint        # ruff check src/aria tests examples
make format      # ruff format src/aria tests examples
make demo        # python examples/run_demo.py
make migrate     # alembic upgrade head (optional — DB not required)
make worker      # celery -A aria.worker worker
make docker-up   # Postgres (pgvector:pg16) + Redis 7
python -m pytest --noconftest tests/test_skills.py -q  # focused skills, offline/no shared_core import
```

## Entry Point

`src/aria/main.py` — FastAPI app. On import it runs the DB-availability probe
(`aria.db.check_db`) and selects persistent or in-memory stores, then wires the
registry, router, approval gate, and per-request agents.

## Source Modules

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app + all endpoints; store/agent wiring |
| `agents.py` | `AriaAgent` — reason/route/approve/act loop; `RunResult` |
| `routing.py` | `KeywordRouter`, `LLMRouter`, `RouteDecision`, `build_router` |
| `llm_client.py` | `AgentLLMClient` — offline-first LLM wrapper |
| `tools.py` | `ToolRegistry`, `Permission`, `build_default_registry` |
| `skills.py` | bounded `SKILL.md` discovery, explicit activation sessions, context reports |
| `builtin_tools/` | calculator (AST), web_search, file_reader (sandboxed), task_creator, email_draft |
| `approvals.py` | `ApprovalGate` (free-running / approval-gated) |
| `memory.py` | `AgentMemory` + `PersistentMemory` + `get_memory` |
| `store.py` / `store_db.py` | in-memory + DB stores for runs/tasks/approvals |
| `db.py` | DB probe + store selection |
| `models.py` | SQLAlchemy models (agent_runs, memory_messages, approvals, created_tasks) |
| `costs.py` | `CostTracker` over `shared_core.llmmetrics` |
| `tracing.py` | `TraceLog` → `shared_core.tracing.Span` trees |
| `worker.py` | Celery tasks: `aria.run_agent`, `aria.sweep_expired_approvals` |
| `config.py` | `AppConfig(BaseAppConfig)` — agent mode/routing, probe timeout |

## API Endpoints

`POST /agent/chat` · `GET /agent/runs` · `GET /agent/runs/{id}` ·
`GET /agent/trace/{id}` · `GET /approvals` · `GET /approvals/{id}` ·
`POST /approvals/{id}/approve` · `POST /approvals/{id}/reject` ·
`GET /tools` · `GET /tools/{name}` · `GET /health`

## shared-core usage

config (`BaseAppConfig`), database (`Base`, mixins, `DatabaseManager`), errors
(`application_error_handler`), logging (`setup_logging`), health (`check_health`),
llm (`LLMClientFactory`), pricing (`calculate_cost`), llmmetrics (`LLMMetrics`),
tracing (`Span`, `SpanType`, `new_trace_id`), clients (`BaseHTTPClient`), tasks
(`create_celery_app`), testing (`MockDatabase`, `MockRedisClient`).

## Tests

`tests/` — unit (tools incl. AST + sandbox safety, routing, memory, approvals,
costs/tracing, stores), integration (agent loop), API (every endpoint + errors),
worker, and focused skill tests. The full suite uses `shared_core.testing` mocks;
the focused skills command above has no `shared_core` dependency.

## Conventions

- Offline-first / real-when-keyed for every external effect.
- Tools return strings (never raise to the caller); the registry validates args.
- Add new tools via `build_default_registry`; mark side-effecting tools
  `Permission.REQUIRES_APPROVAL`.
- Keep cost on `shared_core.llmmetrics` and tracing on `shared_core.tracing`;
  golden tests assert numeric parity with `shared_core.pricing`.
- Skill discovery is offline and metadata-first. Project scope requires
  `trust_project=True`; instruction bodies enter context only through explicit
  `SkillSession` activation, and the existing tool approval loop stays in
  control.

## When to Update This File

Update when tools/endpoints/modes change, the persistence model changes, new
shared-core modules are adopted, or the routing strategy changes.
