# Entrypoints

- `aria.agents.AriaAgent.run(query) -> str` — legacy-compatible response string.
- `aria.agents.AriaAgent.run_structured(...) -> RunResult` — trace, cost,
  approval, and status metadata.
- `POST /agent/chat` — persisted/in-memory structured run.
- `POST /agent/chat/stream` — ordered SSE events from the same engine.
- `POST /agent/runs/{run_id}/replay` — dry-run trace replay by default.
- `GET /agent/memory/search` — local hashed-vector memory inspection.
- `python examples/run_demo.py` — deterministic framework demonstration.
- `python scripts/portfolio_demo.py` and
  `python scripts/verify_portfolio_evidence.py` — portfolio proof bundle.
