# Entrypoints

- `aria.agents.AriaAgent.run(query) -> str` — legacy-compatible response string.
- `aria.agents.AriaAgent.run_structured(...) -> RunResult` — trace, cost,
  approval, and status metadata.
- `POST /agent/chat` — persisted/in-memory structured run.
- `POST /agent/chat/stream` — ordered SSE events from the same engine.
- `GET /agent/runs` / `GET /agent/runs/{run_id}` — persisted or in-memory run
  list and detail; `session_id` filters are additive.
- `POST /agent/runs/{run_id}/replay` — dry-run trace replay by default.
- `GET /agent/memory` — session-isolated conversation memory with reconciled
  approval outcomes.
- `GET /agent/memory/search` — local hashed-vector memory inspection.
- `GET /skills` — catalog metadata plus immutable saved skill evidence for a
  selected or latest run; a read never activates a skill.
- `GET/POST /approvals...` — queue listing, approve/reject, and the optional
  local sweeper.
- `GET /tools` / `GET /tools/{name}` — registered tools, permissions and schemas.
- `GET /health` — dependency health plus safe runtime/persistence metadata.
- `python examples/run_demo.py` — deterministic framework demonstration.
- `python scripts/portfolio_demo.py` and
  `python scripts/verify_portfolio_evidence.py` — portfolio proof bundle.
