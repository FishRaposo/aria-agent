# ARIA — Agent Control Console

A Next.js 16 (React 19) console for inspectable, permissioned agent execution. The opening
screen offers a three-minute guided demonstration and free exploration. The
interactive sample shows a safe calculation, a draft requiring review, and an
unauthorized action denied at the tool boundary.

## Run the sample

```bash
npm ci
npm run demo:ui
```

Open http://localhost:3000. The persistent **Interactive sample data** label
identifies a simulation with no backend or provider calls. Decisions, run
outcomes, and fixture chat share one in-memory state in this tab. **Reset demo**
and reload restore the original scenarios. A completed approval cannot execute
again; rejected and expired approvals remain unexecuted. Expired actions require
a new review. Chat accepts the three suggested fixture prompts and clearly
identifies unsupported free text.

## Connect the actual project

From the repository root in PowerShell:

```powershell
python -m pip install -e ".[dev]"
$env:AGENT_MODE="approval_gated"
$env:ARIA_SAFETY_MODE="block"
$env:CORS_ALLOWED_ORIGINS="http://localhost:3000"
uvicorn aria.main:app --app-dir src --port 8000
```

In `frontend/`, use `npm run dev` with
`NEXT_PUBLIC_API_URL=http://localhost:8000` and
`NEXT_PUBLIC_DEMO_MODE=false`. Browser access is opt-in through the backend's
explicit origin allowlist. Change that allowlist if the frontend origin differs.
The sample toolbar also offers **Connect API**.

Connected mode uses the actual API. Network and HTTP failures remain visible;
there is no automatic substitution of sample data or simulated decisions. Error
views provide **Retry** and an explicit **Enter sample demo** action. Switching
providers clears incompatible view state. A permission approval and a completed
execution have separate labels; unavailable execution evidence remains unconfirmed.

Copy `.env.example` to `.env.local` to override the defaults. These public
frontend variables must never contain credentials.

## Routes

| Route | Purpose |
| --- | --- |
| `/` | Scenario launcher, guided demo, actual-project and evidence entrypoints. |
| `/runs` | Three sample stories or actual run history, plus existing cost/latency charts. |
| `/runs/[id]` | Request → tool → permission → approval → execution timeline, exact review arguments, and technical trace. |
| `/approvals` | Review decisions, filters, expiry recovery, and authoritative execution status. |
| `/skills` | Catalog versus activated instructions, with activation rationale and permission distinction. |
| `/tools` | Tool permissions and expandable JSON schemas. |
| `/chat` | Deterministic fixture prompts in sample mode, actual chat API in connected mode. |
| `/memory` | Connected mode reads actual `GET /agent/memory` conversation events, including reconciled approval outcomes; sample mode derives messages from its fixtures. |
| `/setup` | Strict local API workflow, engineering evidence paths, native-runtime availability and limits. |

The typed client consumes `/agent/runs`, `/agent/runs/{id}`, `/agent/chat`,
`/agent/memory`, `/tools`, `/tools/{name}`, `/approvals`,
`/approvals/{id}/approve`, `/approvals/{id}/reject`, `/skills`, and `/health`
without changing their wire shapes. The persistent toolbar selects the provider
and the connected session (`default` unless renamed); the choice survives tab
reloads while leaf views reset.

## Verify

```bash
npm test -- --run
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e -- --project=chromium
```

Vitest covers provider separation, immutable action bindings, duplicate decisions,
expiry, shared runs/approvals/chat, and returned execution statuses. Playwright
explicitly forces sample mode and tests the full guided path, free exploration,
reset/reload, keyboard decisions and focus, reduced motion, and 390×844,
768×1024, and 1440×900 viewports. The same run includes an axe-core WCAG 2.1
A/AA scan of every demo route. No live backend is required for these checks.

Two more suites reuse the same config:

```bash
# Connected outage behavior (provider unreachable; errors stay errors until
# the user explicitly retries or enters sample mode)
npm run test:e2e:connected -- --project=chromium

# The same sample+a11y specs against the production build instead of next dev
npm run test:e2e:prod -- --project=chromium
```

An optional `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` chooses an already installed
browser. The default Playwright server is managed by the test runner and is not
reused.

The live real-process gate builds production Next.js, migrates a disposable
SQLite file, launches an actual FastAPI process, and asserts HTTP responses,
UI state and direct SQLite effect counts:

```powershell
npm run test:e2e -- --config playwright.live.config.ts --project=chromium
```

It owns dedicated API `8100` and frontend `3102` ports, refuses to reuse an
occupied test port or the owner's database, and clears provider credentials.
After the suite, `python scripts/verify_connected_evidence.py` from the
repository root verifies the recorded connected evidence bundle.

System fonts keep installation and production builds independent of Google Fonts.
For production, `npm run start` serves a previously built frontend. The existing
Dockerfile and root compose web service remain available.
