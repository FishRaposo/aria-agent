# Project 02 verification record

Evidence dates: 2026-10-22–23, America/Sao_Paulo. Base:
`ad5f6e94ee70ae0e9eabbe79d903f2993234ab0b`. Branch: `feat/aria-portfolio`.
This record covers local implementation, not hosted release approval. Historical
hosted CI belongs to the base commit and has not run on this branch.

## Environment

System Python is 3.14; verification uses an isolated `.venv` with bundled
Python3.12.14. Node24.21.0/npm11.19.0 were used with the declared lockfile. CI uses
Python3.11/Node20; that matrix was not rerun locally or remotely. Installation
used declared `.[dev]` dependencies and `npm ci`; no sibling checkout or provider
credential is needed. Matching Playwright Chromium was installed. Browser plugin
was unavailable, so repository Playwright supplied browser automation.

Windows restricted subprocess/temp ACLs required narrow escalated checks.
Precreated `.pytest-temp` supplies test basetemps. Namespace/dependency scans
exclude ignored environments/caches/builds, while runtime source assertions
remain. See [baseline](portfolio-baseline.md) for original failures and repair.

## Python and package evidence

All commands below ran from the ARIA clone with `.venv/Scripts/python.exe`:

| Command | Observed result |
| --- | --- |
| `-m pytest -q --basetemp=.pytest-temp/final-cors --junitxml=.tmp/python-results.xml` | 302 passed, 1 skipped, 0 errors/failures |
| `-m pytest --noconftest tests/test_skills.py -q --basetemp=.pytest-temp/final-skills` | 12 passed; subset, not added to full-suite count |
| `-m ruff check src/aria tests examples scripts` | Pass |
| `-m ruff format --check src/aria tests examples scripts` | 85 files format-clean |
| `-m pyright --pythonpath <absolute .venv python> src/` | 0 errors, 0 warnings |
| `scripts/portfolio_demo.py` then `scripts/verify_portfolio_evidence.py` | Original golden plus additive strict proof pass |
| `scripts/check_forbidden_dependencies.py` | Pass; no forbidden runtime dependency |
| `-m build` then `scripts/check_wheel_contents.py` | sdist/wheel built, required vendored/core files present |

A fresh `.tmp/wheel-env` installed only the wheel and its declared runtime
dependencies. `pip check` passed. From `.tmp/wheel-probe`, imports of `aria.main`,
core and vendored `BaseAppConfig` resolved inside wheel-env/site-packages. The
optional database probe timed out and selected memory, as documented. The first
probe used the wrong symbol `AppConfig` from the vendored module; correcting the
probe to its actual `BaseAppConfig` passed without a source change.

One test is skipped because Windows lacks permission to create a real native
fixture symlink. Mocked native symlink/reparse denial passes; backend containment
tests use a real directory junction fallback. The upstream Starlette TestClient
emits one httpx deprecation warning; this was not suppressed or treated as failure.

## Behavioral proof

- Real HTTP handlers, memory and file-backed SQLite race tests force overlapping
  callers: exactly one authorized dispatch. Mutable argument/run/action/expiry
  binding, rejected/expired/unbound/unknown/schema-invalid actions deny effects.
- SQL migration and dispose/reopen tests retain completed/failed/claimed records.
  A simulated post-effect crash cannot redispatch. This is not a power-loss test,
  PostgreSQL production validation or exactly-once external delivery guarantee.
- Claimed calls force one attempt even if a permission changes; strict requests
  cannot downgrade mode. Dry-run replay creates no effect.
- Canonical proof adds checksummed `strict-profile.json`: one authorized local
  effect, duplicate denied, zero denied effects, zero dry-run effects. The original
  golden fixture was not rewritten. Raw artifacts stay ignored under
  `artifacts/portfolio/aria-agent-evidence`; regenerate them with the commands above.
- Native protocol/fixture suite: 31 passed, 1 host skip. Safe install/uninstall
  smoke passes. Independent review reproduced partial uninstall on an invalid
  audit path; full preflight now precedes deletion, with six focused uninstall
  tests independently passing. Malformed hooks, forbidden paths, guard failure,
  timeout protocol and skipped/false verification are covered.
- The native benchmark default produced all 60 unavailable cells, native_runs=0,
  null costs, verification not_run and no improvement score. No Claude CLI/model
  trial ran. See [setup evidence boundaries](../examples/coding_agent_setup/README.md).

## Frontend and rendered evidence

From `frontend/`: `npm test -- --run` passed 43 tests; `npm run lint` passed;
`npm run build` produced the production routes. The full sample Chromium command
`npm run test:e2e -- --project=chromium` passed 13 tests. A separately started
connected server with `PLAYWRIGHT_CONNECTED=true` and `PLAYWRIGHT_PORT=3101`
passed 2 outage/retry/explicit-sample-recovery tests. Sample config sets
`NEXT_PUBLIC_DEMO_MODE=true`; outage tests set it false and use an unreachable
backend deliberately. They no longer depend on automatic sample fallback.

Independent parent browser inspection captured all three required widths:
390×844, 768×1024 and 1440×900, with reduced motion. All had zero document overflow,
page errors, unexplained console errors, external requests and backend requests
on the sample journey. Keyboard skip-link, decision focus, pause/resume/reset,
cross-route shared state, expiry/new-review, double-click single execution and
unsupported-prompt honesty pass. Screenshot review caught clipped navigation
inside its own scroll container (despite no document overflow): the new assertion
failed at390/768, then all three widths passed after the responsive repair.
The complete sample suite passed again. Screenshots were regenerated and viewed.

The healthy connected probe used the local strict API on8000, a real SQLite file,
keyword routing, no provider keys and explicit CORS origin `http://localhost:3200`.
The browser submitted a task through Chat, loaded its approval, approved it through
the queue, and observed execution completed. A repeated browser POST returned409.
A direct SQLite query confirmed exactly1 task and one approved/completed record.
All observed API requests had expected200/409 responses; no unexplained browser
error occurred. This is real local API/store/tool evidence, not sample playback.

| Screenshot | Scope |
| --- | --- |
| [Desktop opening](images/portfolio-home-1440.png) | Guided/free entry, sample label, setup/evidence links |
| [Tablet opening](images/portfolio-home-768.png) | All navigation controls fit |
| [Mobile opening](images/portfolio-home-390.png) | Stacked content and readable actions |
| [Approval timeline](images/portfolio-approval.png) | Exact arguments, decision boundary, zero effects while pending |
| [Denied action](images/portfolio-denied.png) | Permission denial before execution |
| [Skills](images/portfolio-skills.png) | Catalog versus activated content |
| [Actual connected result](images/portfolio-connected.png) | Local task effect, completed execution, no simulation label |

Accessibility checks are bounded browser/visual/keyboard checks; no formal
screen-reader or full WCAG conformance audit is claimed. The current connected
backend has no `/skills` snapshot endpoint; that route shows a real404 error and
does not substitute the sample skill catalog. Native setup uses its own fixture.

## Review and remaining boundaries

An independent reviewer inspected backend/native changes and frontend state/API
views. All four findings were repaired and independently rechecked: native
uninstall preflight (6 tests), connected execution labels and expiry-at-click
notices (8 component tests), explicit CORS integration (15 API/config tests).
The final bounded review has no unresolved actionable finding. The report is
preserved in ignored `.tmp/review-report.md`; this is not security certification.

The operation workspace overview checksum guard passes. Its broad validator
reports 960 errors across archives, cloned repositories, installed dependencies and generated fixture/cache
paths. Its unit harness copies the entire workspace including dependency trees;
that run was interrupted before an assertion result. These are not ARIA suite
results, and no broad-workspace green claim is made. The parent has no `.git`;
portfolio numbering and handoff files cannot receive a parent-repository commit.

No public hosting, publication, recording, paid provider usage, native account
access, real secret fixture, customer artifact or cash receipt was introduced.
Other five application working trees remain outside this milestone. IDs:
AR-01–AR-06, existing FTH-016; no opportunity/experiment/cash ledger change.
