# ARIA — Agent Control Console (frontend)

A polished Next.js 14 dashboard for the **ARIA agent framework**. It is the
operator console for an autonomous agent: browse runs, inspect span-level
traces, chat with the agent live, review the tool registry, govern risky tool
calls through an approval queue, and inspect conversation memory — with cost and
latency charts throughout.

> Built to match the portfolio web toolchain: Next.js 14 (App Router) + React 18
> + TypeScript + Tailwind + lucide-react + recharts + react-markdown, tested with
> Vitest + @testing-library/react (jsdom) and Playwright.

## Pages

| Route          | What it shows                                                                                 |
| -------------- | --------------------------------------------------------------------------------------------- |
| `/`            | Overview / landing.                                                                            |
| `/runs`        | Run list with aggregate cost/token/latency stats and **cost-per-run** + **latency-per-run** charts. |
| `/runs/[id]`   | Run detail: response, cost summary, and a **trace timeline** (spans, durations, status) + step log. |
| `/chat`        | Chat panel driving the reason-and-act loop — tool calls, approval gating, and per-message cost. |
| `/tools`       | Tool registry: each tool's description, JSON schema, and permission level (safe / requires-approval). |
| `/approvals`   | Approval queue with status filters and **approve / reject** buttons.                          |
| `/memory`      | Memory inspector for a session's conversation history.                                        |

## Backend endpoints consumed

The typed client in [`src/lib/api.ts`](src/lib/api.ts) talks to the ARIA
FastAPI service:

- `GET  /agent/runs` — run list
- `GET  /agent/runs/{id}` — run detail (trace + cost)
- `POST /agent/chat` — run the agent on a message
- `GET  /tools` — tool registry
- `GET  /approvals?status=` — approval queue
- `POST /approvals/{id}/approve` · `POST /approvals/{id}/reject`
- `GET  /health` — dependency health

The Memory inspector derives session history from `GET /agent/runs` when live
(the backend persists memory but exposes no read route).

## Run it

```bash
cd frontend
npm install
npm run dev          # http://localhost:3000
```

Point it at a backend with `NEXT_PUBLIC_API_URL` (default
`http://localhost:8000`). To run the ARIA API locally:

```bash
# from the repo root
uvicorn aria.main:app --app-dir src --host 0.0.0.0 --port 8000
```

### Environment

| Variable              | Default                 | Purpose                          |
| --------------------- | ----------------------- | -------------------------------- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Base URL of the ARIA FastAPI backend. |

Copy `.env.example` to `.env.local` to override.

## Demo mode (no backend required)

The dashboard is **live-first with a graceful demo fallback**, so every view is
fully explorable with **no backend running**:

- Each request tries the real backend first.
- If the backend is **unreachable** (network failure), the view falls back to
  bundled mock data ([`src/lib/mockData.ts`](src/lib/mockData.ts)) and shows a
  visible **"Demo mode"** badge explaining why.
- A real **HTTP 4xx/5xx is surfaced as an error state** — never masked by mock
  data — so backend problems stay visible.
- In demo mode, **writes** (chat in approval-gated mode, approve/reject) run a
  local simulation and display a **"demo — not persisted"** notice.

In demo mode the Chat panel even runs a small local reason-and-act loop, so you
can watch routing, tool calls, the approval gate, and cost without any server.

Just run `npm run dev` and open the app — no backend needed.

## Tests

```bash
npm run test         # Vitest component + api-client tests (no backend needed)
npm run test:e2e     # Playwright smoke E2E over the demo-mode UI
```

- **Vitest** (`tests/`) renders the key components/views against bundled mock
  data with `fetch` stubbed to simulate a down backend, and asserts the
  demo-mode fallback, error surfacing, charts, trace timeline, approval flow,
  and chat loop. All tests pass with no backend.
- **Playwright** (`e2e/smoke.spec.ts`) drives the live demo-mode UI: home,
  runs + charts, run detail trace, tools registry, approval controls, and a
  chat turn.

## Build

```bash
npm run build        # next production build
npm run start        # serve the production build
```

## Docker

A multi-stage `Dockerfile` is provided. The repo's root `docker-compose.yml`
includes a `web` service:

```bash
docker compose up web
```
