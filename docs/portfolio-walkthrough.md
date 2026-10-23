# Three minutes with ARIA

## Recruiter preview

Install frontend dependencies with `npm ci`, then `npm run demo:ui` from
`frontend/` and open `http://localhost:3000`. This is an interactive sample,
independent of provider accounts, backend services and sibling projects.

| Time | Interaction | Explain |
| --- | --- | --- |
| 0:00–0:25 | Start guided demo; open the safe calculation | A request becomes validated tool input and a visible result. |
| 0:25–1:00 | Inspect the risky draft and its exact arguments; reject it | Human review is a separate decision. Rejection means not executed. |
| 1:00–1:35 | Reset, approve the unchanged draft, inspect the result | This is one simulated execution. A used approval cannot run again. |
| 1:35–2:00 | Inspect expiry, request a fresh review, then open the denied story | Recovery creates a new request. Instructions do not confer permissions. |
| 2:00–2:30 | Inspect skills and expandable technical details | Catalog visibility differs from actual content activation. |
| 2:30–3:00 | Open setup/evidence; explain the real workflow | UI simulation, local enforcement tests and native model trials are different evidence. |

Free exploration supports the same stories. Reset restores runs, approvals,
skills and tour together. Use keyboard navigation and Escape/close controls for
overlays; sample status and decisions are always textual. Connected-mode failures
offer Retry and an explicit switch to sample; no successful fixture result is
silently substituted.

## Actual project: local strict execution

Use a fresh terminal and the declared Python environment:

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -e ".[dev]"
$env:AGENT_MODE = "approval_gated"
$env:ARIA_SAFETY_MODE = "block"
$env:CORS_ALLOWED_ORIGINS = "http://localhost:3000"
.venv/Scripts/python.exe -m uvicorn aria.main:app --app-dir src --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs`. Use `POST /agent/chat` with a task-creation
request (for example, `{"message":"create a task to review evidence"}`). Inspect
the pending approval, then approve its ID through the OpenAPI approval endpoint.
Read the returned trace and execution metadata. Repeating approval cannot
dispatch a second effect. Reject another request, and inspect its nonexecution.
The project creates local task/email artifacts; it does not send email.

For a connected dashboard, launch `npm run dev` with
`NEXT_PUBLIC_DEMO_MODE=false` and `NEXT_PUBLIC_API_URL=http://localhost:8000`.
Restart the frontend after changing public environment values; Next.js captures
them at build/start. Sample mode deliberately simulates its own local stories.

The CORS origin is opt-in and must match the frontend's scheme, hostname and port.
Use a comma-separated explicit list if needed. The default is disabled; wildcards
and credentialed origins are not supported. CORS is not authentication and does
not make the API suitable for public exposure.

For existing SQL installations, back up the development database, configure the
same database URL used by the server, then run `alembic upgrade head` before
starting this version. Migration `0002_approval_execution_claim` adds binding and
execution metadata. Table creation alone does not alter old tables. Old unbound
approval rows fail closed and require a fresh request. In-memory state is lost
on process exit; it is not durable restart evidence. Automated restart tests use
an actual file-backed SQLite database; PostgreSQL deployment remains unverified.

Generate/verify the credential-free proof with the commands in
[the case study](portfolio-case-study.md). Build/install the wheel independently
to inspect package isolation; see [verification](portfolio-verification.md).

## Setup engagement handoff

Read the [native fixture guide](../examples/coding_agent_setup/README.md).
Inspect canonical skills, settings, guard audit and independent verifier.
Install into a new synthetic destination, run protocol tests, generate the
unavailable-cell report, then uninstall/restore using the documented safe path.
There is no native quality score to present yet. The owner supplies runtime,
model, isolation evidence and budget only if native trials are later authorized.

Recording/uploading/hosting is outside this implementation. This text is the
recording script; no video recording is claimed.
