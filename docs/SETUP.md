# Setup

ARIA’s supported local setup is:

```bash
python -m venv .venv
python -m pip install -e ".[dev]"
python examples/run_demo.py
```

The API runs with `uvicorn aria.main:app --reload --app-dir src`. No database,
Redis service, provider key, or network-backed evaluation is needed. Use
`make docker-up` only for optional PostgreSQL/Redis integration work.

Run the canonical Python and frontend verification commands from `AGENTS.md`.
The dated results belong in `README.md` and `docs/TESTS.md`; setup instructions
remain stable when test counts change.

## Portfolio experiences

From `frontend/`, run `npm ci` then `npm run demo:ui`. The visual sample has
populated scenarios, guided/free exploration and reset; no backend/provider
or network font is required. Connected mode uses `npm run dev` with
`NEXT_PUBLIC_DEMO_MODE=false` and the local `NEXT_PUBLIC_API_URL`. Transport
errors stay visible until Retry or an explicit sample-mode switch.

Use the [walkthrough](portfolio-walkthrough.md) for the strict Python API launch,
real approval path and existing-database migration. The [native fixture guide](../examples/coding_agent_setup/README.md)
provides install/uninstall and credential-free protocol checks. Native runtime
trials require separately authorized access/model/budget; none ran locally.
