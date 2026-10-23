# ARIA connected application — 2026-10-23

The connected console now inspects actual saved execution, skill and conversation
evidence. It uses the same visual language as the recruiter preview. Its data
comes from FastAPI and the configured stores; the preview remains a separate,
explicitly labeled simulation.

This milestone follows `913fefaf1b18033f597be46fa2c1a95f80703731` on
`feat/aria-portfolio`. It implements the owner's approved connected application
plan. [Verification](portfolio-verification.md) records fresh results and limits;
[handoff](portfolio-handoff.md) records the integration state. It does not add
hosting, accounts, authentication or provider trials.

## What a reviewer can do

1. Choose a session in the persistent toolbar. Quick starts prepare a request;
   they never submit it automatically.
2. Send `calculate 7 * 8`. Inspect its saved run and request-to-execution timeline.
3. Open Skills. Select that run to inspect why `calculator` matched, its source
   identifier, SHA-256 and the exact instructions loaded into prepared context.
   Keyword routing does not consume them through a model.
4. Submit `create a task to review evidence`. Inspect the exact proposed
   parameters, approve once, and see the completed result across Runs, Chat,
   Approvals and Memory. Repeated approval cannot dispatch the tool again.
5. Try a draft, rejection or `read ../outside.txt`. Drafting creates local text;
   it sends no email. The file example exercises the actual sandbox boundary.
6. Switch sessions and reload. Provider and session survive tab reload; saved
   history stays separate. Sample scenarios still reset on reload/reset.
7. Stop the API. Errors stay errors. Retry after recovery, or explicitly enter
   the sample demo. No successful sample response substitutes for a failed call.

## Strict local setup with durable SQLite

Run from the repository root in PowerShell. Use your declared project Python
environment. The paths below create synthetic local review data in `.tmp`.

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
New-Item -ItemType Directory -Force .tmp/connected-review/sandbox | Out-Null
Set-Content .tmp/connected-review/sandbox/notes.txt 'Synthetic local runbook.'
Set-Content .tmp/connected-review/outside.txt 'Outside the configured sandbox.'
$env:DATABASE_URL = 'sqlite:///' + ((Join-Path $PWD '.tmp/connected-review/app.db') -replace '\\','/')
$env:ARIA_SANDBOX_DIR = Join-Path $PWD '.tmp/connected-review/sandbox'
$env:AGENT_MODE = 'approval_gated'
$env:ARIA_SAFETY_MODE = 'block'
$env:AGENT_ROUTING = 'keyword'
$env:OPENAI_API_KEY = ''
$env:ANTHROPIC_API_KEY = ''
$env:ARIA_SEARCH_API_URL = ''
$env:CORS_ALLOWED_ORIGINS = 'http://localhost:3000'
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn aria.main:app --app-dir src --host 127.0.0.1 --port 8000
```

In a second terminal, from `frontend/`:

```powershell
npm ci
$env:NEXT_PUBLIC_DEMO_MODE = 'false'
$env:NEXT_PUBLIC_API_URL = 'http://127.0.0.1:8000'
npm run dev
```

Open `http://localhost:3000`. A tab that previously selected sample mode remembers
that choice: select **Connect API**. CORS must match the browser origin exactly.
Restart Next.js after changing public environment values. These are explicit
launch settings; library defaults remain compatible. Existing database owners
should back up their development database before applying migrations.

## Skill selection and truthful evidence

The five canonical sources live in `.agents/skills`: `calculator`, `task-creator`,
`email-draft`, `file-reader` and `web-search`. Build output copies those resources
to `aria/_skills` in the wheel. Source distributions include the canonical files.
An installed package does not depend on its checkout, current directory, home
skills or sibling repositories.

Every API run gets a new skill session. Deterministic selection reuses tool-intent
rules, bounds multi-step selection by the execution step limit and deduplicates
matches. An explicit known `/skill-name` overrides matching; unmatched text loads
no instructions. Generic library sessions retain their explicit activation default.

Discovery reads bounded metadata. Loading revalidates identity, encoding, body
size and resolved source containment. Missing, invalid or escaped selected content
blocks execution. Skills never widen tool permissions. Public sources use logical
identifiers such as `builtin:calculator/SKILL.md`.

`GET /skills?session_id=default&run_id=...` reads recorded evidence. Omitting the
run ID selects the latest saved run in that session. Before its first run, the
endpoint returns catalog metadata with no bodies. A read never activates a skill.
Saved bodies, hashes, matching method and reasons survive later source changes.
Historical records without snapshots remain explicitly unknown.

“Loaded into prepared context” is different from “consumed by a model.” Keyword
runs record `context_consumed=false`; this establishes neither model use nor skill
effectiveness. Web search without an explicitly configured service returns its
clearly labeled deterministic simulation. This local path is not internet research.

## Persistence and approval authority

Migration `0003_connected_app` adds nullable run session/skill/approval fields,
execution result/trace and unique memory event keys. Old rows retain unknown
session/evidence. Both chat and SSE save the same immutable skill evidence.

Approval statuses remain pending, approved, rejected and expired. Execution has
separate not-claimed, claimed, completed or failed metadata. Existing atomic
claims and immutable argument/run binding still decide dispatch. Presentation
reads project authoritative outcomes without invoking a tool:

| Authority | Run view | Human explanation |
| --- | --- | --- |
| Pending review | pending_approval | Awaiting a decision; no execution claim |
| Completed execution | completed | Stored result and execution trace |
| Failed execution | error | Failure result and trace; no automatic redispatch |
| Rejected/expired | blocked | No authorized execution |
| Claimed, no final outcome | pending_approval | Outcome unconfirmed; reconcile the effect before any new request |

Final outcomes append once to the originating conversation with a durable event
key. Repeated reads, concurrent reconciliation and restart cannot duplicate that
message. A process stopping between execution persistence and presentation can
recover missing memory updates by reading history or starting the next chat.
Recovery cannot establish whether an external side effect happened after an
unconfirmed claim; it never retries that action automatically.

`GET /agent/memory?session_id=...&limit=50` reads actual conversation memory.
Connected lists use session filters. Omitted filters retain legacy unfiltered API
behavior. Session IDs organize a local workspace; they are not authorization or
tenant isolation. This application remains a local, trusted-user deployment.

Health exposes safe runtime metadata: execution mode, allowed modes, routing,
automatic skill selection and persistence availability. Strict deployments disable
unsupported mode controls. Redis can remain unavailable while SQLite works.

The recovery path currently walks saved session history. It is intentionally
simple for this local workload; pagination/background recovery and hosted scale
must be evaluated before making a multi-user deployment claim.

## Reproduce the connected proof

From `frontend/`, with the project environment and Chromium installed:

```powershell
npm run test:e2e -- --config playwright.live.config.ts --project=chromium
```

The harness owns dedicated API8100 and Next3102 processes, refuses an occupied
test port and creates `.tmp/live-e2e-*/app.db`. It migrates that file and restarts
the API against the same file. It never reuses the owner's running database.
Override `ARIA_TEST_PYTHON`, `ARIA_LIVE_API_PORT` or `ARIA_LIVE_FRONTEND_PORT` for
another environment. Successful application responses are never mocked. Provider
keys and search service configuration are cleared; routing is forced to keyword.

The workflow verifies HTTP responses, UI state, direct SQLite effect counts,
duplicate409 and identical historical skill evidence after restart. Other cases
cover actual expiry, denial, rejection, failing SQLite task insertion, streaming,
legacy unknowns, outage/retry, explicit sample switching and three responsive
sizes. The uncertain-claim test seeds a persisted interruption state; it does not
claim to have crashed a process during an external side effect.

After the suite, from the root:

```powershell
.venv/Scripts/python.exe scripts/verify_connected_evidence.py
```

The separate ignored `artifacts/portfolio/connected-evidence` bundle contains
checksummed observations, a stable semantic summary and provenance. Its verifier
checks recorded instruction hashes, outcomes and acceptance criteria. The original
golden evidence remains unchanged. Checksums show artifact integrity, not security
certification or independent observation. Regenerate evidence from the harness.

## Acceptance boundaries

Local Python/SQLite/browser/package checks support this delivered workflow.
Fresh commands and counts are in [verification](portfolio-verification.md).
Native Claude/model trials, paid providers, hosted CI for this branch,
PostgreSQL deployment, arbitrary power-loss behavior and public multi-user
authentication remain unverified or outside scope. Keyboard/visual checks do not
constitute a formal accessibility certification. No external message, publication,
customer result or cash receipt was introduced.
