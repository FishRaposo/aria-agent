# AGENTS.md — aria-agent

## What This Is

Aria Agent (ARIA — Agentic Reasoning & Integration Architecture) — a lightweight AI agent framework with controlled tool execution, Pydantic-validated schemas, human approval gates, and conversation memory. Currently at skeleton stage with a working agent loop, tool registry, and approval gate — but using keyword-based routing (not LLM-based) and in-memory state only. Part of Wave 2 in the showcase portfolio build plan.

> **Not related to NousResearch/hermes-agent** — the previous package name `hermes` was renamed to `aria_agent` to avoid confusion with the upstream fork. The framework's own agent class is `AriaAgent` (not `HermesAgent`).

## Commands

```bash
make install          # pip install -e ../shared-core && pip install -r requirements.txt
make dev              # uvicorn on :8000 via src/aria_agent/main.py
make test             # pytest (tests/test_core.py)
make lint             # ruff check .
make format           # ruff format .
make typecheck        # pyright src/
make docker-up        # docker compose up -d (Postgres pgvector:pg16 + Redis 7)
make docker-down      # docker compose down
make demo             # python examples/run_demo.py (calculator agent flow)
make clean            # remove __pycache__, .pytest_cache, etc.
```

## Entry Point

`src/aria_agent/main.py` — FastAPI app that imports:
- `AppConfig` from `aria_agent.config` (extends `shared_core.config.BaseAppConfig`)
- `ToolRegistry` from `aria_agent.tools`
- `AriaAgent` from `aria_agent.agents`
- `ApprovalGate` from `aria_agent.approvals`
- `DatabaseManager`, `RedisManager` from `shared_core`
- `setup_logging` from `shared_core.logging`

Exposes two endpoints: `POST /agent/chat` and `GET /health`.

## Source Modules

| File | Purpose |
|------|---------|
| `src/aria_agent/__init__.py` | Package marker |
| `src/aria_agent/main.py` | FastAPI app, wires agent + registry + gate, health check |
| `src/aria_agent/agents.py` | `AriaAgent` class — run loop with tool selection, approval, memory |
| `src/aria_agent/tools.py` | `ToolRegistry` — decorator-based tool registration, Pydantic schema validation via `call_tool()` |
| `src/aria_agent/memory.py` | `AgentMemory` — in-memory message list with `add_message()` and `get_context()` |
| `src/aria_agent/approvals.py` | `ApprovalGate` — human-in-the-loop checkpoint (currently auto-approves) |
| `src/aria_agent/config.py` | `AppConfig` extending `BaseAppConfig` with `APP_NAME = "aria-agent"` |
| `src/aria_agent/errors.py` | `application_error_handler` — global FastAPI handler for `BaseApplicationError` |
| `src/aria_agent/worker.py` | Celery app configured with Redis broker, `sample_background_task` stub |
| `examples/run_demo.py` | Registers calculator tool, runs agent with approval gate |
| `tests/test_core.py` | Health endpoint test |

## Docker Services

- **postgres**: `pgvector/pgvector:pg16` on `:5432` (container: `aria_postgres`)
- **redis**: `redis:7-alpine` on `:6379` (container: `aria_redis`)

## Layout

```
src/aria_agent/
├── __init__.py          # Package init
├── main.py              # FastAPI app, POST /agent/chat, GET /health
├── agents.py            # AriaAgent.run() — reason-and-act loop
├── tools.py             # ToolRegistry.register(), .call_tool()
├── memory.py            # AgentMemory — message list store
├── approvals.py         # ApprovalGate.request_approval()
├── config.py            # AppConfig (pydantic-settings)
├── errors.py            # Global error handler
└── worker.py            # Celery worker + sample task
docs/
├── architecture.md
├── design-decisions.md
├── failure-modes.md
├── roadmap.md
└── security.md
examples/
└── run_demo.py          # Calculator agent demo
tests/
└── test_core.py         # Health endpoint test
```

## Current State

**Skeleton with working proof-of-concept.** The core agent loop works end-to-end for a single tool (calculator), but:
- Tool routing is keyword-based (`if "calculate" in user_query.lower()`), not LLM-backed
- `ApprovalGate` always auto-approves (logs warning but returns `True`)
- `AgentMemory` is in-memory only (Python list, no persistence)
- Worker has a stub task only (`sample_background_task`)
- No tracing, cost tracking, or retry policies implemented yet
- Only one tool registered in the demo (calculator)

## Key Dependencies

Beyond shared-core:
- `celery>=5.3.0` — background task execution for async tool runs
- `loguru>=0.7.0` — structured logging in agent and approval modules
- `httpx>=0.24.0` — async HTTP client for external tool calls (web_search_mock etc.)
- `pyyaml>=6.0.0` — planned for workflow definition files

## When to Update This AGENTS.md

Update when:
- New tools are added to the registry or `examples/`
- Agent routing changes from keyword-based to LLM-based
- `AgentMemory` gains persistence (database-backed)
- `ApprovalGate` gets a real approval queue (async with timeout)
- New modules added under `src/aria_agent/` (tracing/, costs/, prompts/)
- Celery worker gets real agent tasks instead of stub
- New API endpoints added beyond `/agent/chat` and `/health`
- Docker Compose services change (e.g., adding a message queue for approvals)
