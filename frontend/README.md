# ARIA — Agent Control Console

A Next.js 14 console for inspectable, permissioned agent execution. The opening
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
| `/memory` | Conversation inspector derived from the current provider's run history; the backend has no memory-read route. |
| `/setup` | Strict local API workflow, engineering evidence paths, native-runtime availability and limits. |

The typed client consumes `/agent/runs`, `/agent/runs/{id}`, `/agent/chat`,
`/tools`, `/tools/{name}`, `/approvals`, `/approvals/{id}/approve`,
`/approvals/{id}/reject`, `/skills`, and `/health` without changing their wire shapes.

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
768×1024, and 1440×900 viewports. No live backend is required for these checks.

Run the separate connected outage test against its own server in PowerShell:

```powershell
$env:PLAYWRIGHT_CONNECTED="true"
$env:PLAYWRIGHT_PORT="3101"
npm run test:e2e -- --project=chromium
```

Unset those variables before running the sample suite again. An optional
`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` chooses an already installed browser.
The default Playwright server is managed by the test runner and is not reused.

System fonts keep installation and production builds independent of Google Fonts.
For production, `npm run start` serves a previously built frontend. The existing
Dockerfile and root compose web service remain available.
