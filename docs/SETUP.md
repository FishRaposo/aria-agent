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
