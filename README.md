# ARIA Agent Framework

Canonical clean-break agent harness: approval gates, execution tracing, and progressive-disclosure Agent Skills.

![Python](https://img.shields.io/badge/Python-3.10+-3776ab?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-blue)

ARIA is an offline-first agent harness for demonstrating controlled execution.
The default demo uses deterministic routing, local tools, in-memory state, and
no credentials or network. PostgreSQL, Redis, Celery, and real model providers
are optional integration surfaces; none is required to run the suite.

## What is shipped

- Schema-validated tools with `safe` and `requires_approval` permissions.
- A compatibility-preserving `AriaAgent.run()` string API and structured
  `RunResult` API.
- A bounded single-hop default and opt-in deterministic multi-hop plan mode.
- Deterministic safety classification (`off`, `warn`, `block`), injectable retry
  policies, and fixed-window per-session/tool rate limiting.
- Approval queues with lazy expiry, an optional local sweeper, and the existing
  Celery sweep task.
- AgentTrace-compatible spans, cost summaries, replay with dry-run default, and
  ordered SSE events at `POST /agent/chat/stream`.
- A pure-Python hashed-vector memory index at `GET /agent/memory/search`.
- Progressive-disclosure Agent Skills with explicit activation and trust rules.
- A self-contained vendored compatibility subset under
  `src/aria/internal/vendor_core/`, pinned and attributed in
  `THIRD_PARTY_NOTICES.md`.
- A reproducible offline evidence bundle and golden fixture.

## Quick start

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
python -m pip install -e ".[dev]"
python examples/run_demo.py
python scripts/portfolio_demo.py
python scripts/verify_portfolio_evidence.py
uvicorn aria.main:app --reload --app-dir src
```

The canonical install path is `pip install -e ".[dev]"`. Docker Compose is
optional and only starts PostgreSQL and Redis for integration work.

## Offline evidence path

`make evidence` runs a fixed SQLite-free scenario covering routing, bounded
multi-hop execution, safety decisions, retries, rate limits, approval state,
dry-run replay, streaming event order, local memory ranking, costs, and traces.
The generated bundle lives under ignored `artifacts/portfolio/aria-agent-evidence`.
It contains `manifest.json`, canonical `report.json`, `report.md`, and
`checksums.sha256`; `scripts/verify_portfolio_evidence.py` rejects tampering,
missing files, malformed manifests, and golden-result drift.

Secrets are redacted by key and by common bearer/API-key patterns. Timestamps,
runtime durations, generated IDs, and environment paths are excluded from the
reproducibility hash, while the raw report remains inspectable locally.

## API surface

| Method | Path | Purpose |
|---|---|---|
| POST | `/agent/chat` | Run the agent and return the legacy-compatible structured result |
| POST | `/agent/chat/stream` | Stream ordered reasoning, decision, approval, tool, error, and completion events as SSE |
| GET | `/agent/runs` | List recent persisted or in-memory runs |
| GET | `/agent/runs/{id}` | Fetch a run with trace and cost |
| POST | `/agent/runs/{id}/replay` | Replay a trace; dry-run is the default |
| GET | `/agent/memory/search` | Inspect deterministic local memory matches |
| GET/POST | `/approvals...` | Inspect and decide approval-queue records; optional `/approvals/sweep` |
| GET | `/tools...` | Inspect registered tools and schemas |
| GET | `/health` | Report database/Redis dependency health |

Existing response keys, route vocabulary, approval lifecycle, cost numbers, and
trace span vocabulary remain stable. New execution metadata is additive.

## Development gates

```bash
pytest -q
pytest --noconftest tests/test_skills.py -q
ruff check src/aria tests examples scripts
ruff format --check src/aria tests examples scripts
pyright src/
make evidence
make package
make forbidden

cd frontend
npm ci
npm test -- --run
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e -- --project=chromium
```

### Verified snapshot — 2026-08-14

| Surface | Fresh result |
|---|---|
| Python suite | 200 passed |
| Focused progressive-disclosure skills | 12 passed (focused subset, not added to 200) |
| Ruff | Check passed; 72 files format-clean |
| Pyright | 0 errors |
| Evidence | Generated and verified against the golden fixture |
| Package | sdist/wheel built; vendored wheel contents verified |
| Frontend | 31 Vitest tests, lint, and production build passed |
| Browser smoke | 6 passed locally in Chromium (reverified 2026-08-15) |

On this Windows host the default global pytest temp directory was inaccessible;
the full suite passed with `--basetemp=.pytest-temp/plan-run`. The Playwright
Chromium smoke suite was re-run locally on 2026-08-15 with all six tests passing.
The CI workflow installs Chromium explicitly before running the same suite.

The dashboard is a read-only portfolio surface and keeps its existing routes.

## Boundaries

The repository deliberately does not require hosted/team tenancy, notification
webhooks, external vector services, OTLP protobuf/gRPC, mandatory Redis or
PostgreSQL, or provider credentials. Those are product directions, not hidden
dependencies. Local abstractions are present so the execution core and its
evidence can be reviewed without infrastructure.

## Project map

- `src/aria/internal/core/` — canonical execution contracts and policies.
- `src/aria/agents.py`, `routing.py`, `tools.py`, `approvals.py`, `memory.py` —
  compatibility facades retained for existing integrations.
- `src/aria/internal/vendor_core/` — attributed, pinned local compatibility
  modules used by the server and worker.
- `scripts/` — evidence generation, verification, wheel, and dependency scans.
- `tests/fixtures/golden/portfolio-evidence.json` — normalized offline proof.
- `frontend/` — dashboard with unit, lint, build, and browser smoke coverage.
- `docs/` — architecture, security, replay, streaming, safety, memory, and
  evidence notes.

## License

MIT. See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
