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
screen-reader or full WCAG conformance audit is claimed. At the first milestone
the connected skills endpoint was absent and failed honestly. The subsequent
[connected milestone](portfolio-connected.md) supplies actual saved evidence;
fresh results below supersede that gap. Native setup uses its own fixture.

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

## Connected application milestone — 2026-10-23

Base `913fefaf1b18033f597be46fa2c1a95f80703731`, same `feat/aria-portfolio`
branch. This section supersedes the first milestone's missing connected-skills
endpoint. [Connected setup/design/proof](portfolio-connected.md) is the current
live workflow; earlier results above remain historical evidence.

| Gate | Fresh result / retained command evidence |
| --- | --- |
| Full Python | 354 passed, 1 host symlink skip, 0 failures/errors; JUnit355 collected, `.tmp/connected-final-python.xml` |
| Focused skills without conftest | 32 passed (`tests/test_skills.py tests/test_connected_skills.py`); subset of full suite |
| Backend integration | 135 passed across connected/API/approvals/stores/boundaries; 29 connected cases, subset |
| Ruff | Check passed; 91 Python files format-clean, including setup hook |
| Pyright | 0 errors, 0 warnings using the absolute project interpreter |
| Canonical evidence | Original golden preserved; generator/verifier and strict proof pass |
| Connected evidence | Separate real HTTP/browser/SQLite bundle verifies, including recorded body SHA256 and outcome uniqueness |
| Packaging | Fresh sdist/wheel build and five canonical wheel assets pass; fresh dependency environment passes pip check |
| Installed wheel | Outside-checkout `-I` probe imports isolated package, discovers5, activates calculator and reads actual API catalog/runtime metadata |
| Frontend unit/lint | 64 passed in17 files; lint clean |
| Production build | All11 routes built with isolated `NEXT_DIST_DIR=.next-connected-build` |

Final Python command:
` .venv/Scripts/python.exe -m pytest -q --basetemp=.pytest-temp/connected-final-2 --junitxml=.tmp/connected-final-python.xml `.
The same upstream Starlette/httpx deprecation and Windows symlink capability limit
remain explicit. A first concurrent full run misclassified two native crash/
malformed probes because interpreter startup exceeded their shared100ms budget.
Their non-timeout probes now allow2s; the deliberate timeout case retains100ms.
The focused suite and full355-collected suite then passed. No native/model trial ran.

The first connected API regression had20 failing behavior assertions. Automatic
skills tests exposed empty selection and actual sandbox escape dispatch. A real
process metadata test failed on an empty catalog, then passed with5. Supplemental
fault/evidence cases were added after the initial implementation; they are not
misrepresented as initial red-first cycles. New evidence-gate tests reject raw
observation tampering, resealed false effect counts and body/hash disagreement.

Browser verification found and repaired issues that source/unit checks missed:
changing sessions remounted Next's route tree, the skip link did not focus main,
Setup's implicit mobile grid overflowed, and live monotonic timestamps caused
trace bars to exceed their tracks. Navigation has a red/green component regression;
chart overflow reproduced150% combined offset/width and now passes. Independent
trace clocks scale separately; raw times remain available. Draft JSON now has a
readable presentation without altering exact backend evidence.

The live harness builds and starts production Next.js before testing actual API
processes. Development hot reload had produced RSC fetch errors when separate
builds changed shared generated type files; final verification uses a frozen
production artifact and no concurrent frontend builds. This is a harness/process
isolation correction, not a console-error suppression. Only intentional connection
refusal in the outage case is classified as expected. All other console/page
errors remain failures.

Bounded independent source review found no remaining actionable issue, including
a focused re-review of session navigation, leaf resets and draft presentation.
The screenshot-driven chart fix has its own focused/full frontend verification.
No hosted CI, PostgreSQL deployment, arbitrary power-loss guarantee, native/model
quality, public authentication or formal accessibility certification is claimed.

The canonical operation overview guard passes. Its broad validator now reports784
errors across archives, cloned repositories, environments/build outputs and skill
placement in independent nested repositories. This is not an ARIA gate. The parent
copy-all unit harness is not rerun in this milestone because it copies complete
clones/dependency environments; its earlier interrupted result remains unverified.
The scoped portfolio documentation/link/number checker passes. Parent has no Git
repository; its index/handoff changes cannot receive a parent commit. No receipt,
opportunity or experiment was added; cash remains unknown.

### Final browser and visual results

Production real-backend command from `frontend/`:
`npm run test:e2e -- --config playwright.live.config.ts --project=chromium`
passed **10/10**. It migrates a fresh SQLite database, uses actual FastAPI and a
production Next process, clears credentials and validates HTTP/SQLite effects.
Calculation → automatic skill inspection → task approval → completed Chat/Run/
Memory → separate session → API restart passes. Draft quick start makes no request
until Send; keyboard approval records drafted/sent=false. Rejection, actual1s
expiry, real sandbox escape denial, actual SQL insertion failure, seeded uncertain
claim, SSE and historical unknowns pass. Duplicate approval returns409; one task
is created only in the authorized case. Repeated memory reads remain identical.

All connected routes (`/`, Chat, Runs/detail, Skills, Memory, Tools, Approvals,
Setup) pass at390×844,768×1024,1440×900 with reduced motion, no document overflow,
no nav-container clipping and no unexplained console/page errors. Keyboard skip
focus and draft approval pass. Actual API shutdown → error → restart → Retry
recovers; explicit sample switching stops backend calls. View selectors and
underlying records both participate in assertions; no successful API response is
mocked. Final output: `.tmp/connected-live-final.log`.

After the shared chart repair, the forced sample command passed **13/13** again;
its guided/free/reset/rejection/expiry and no-backend assertions remain intact.
The original `PLAYWRIGHT_CONNECTED=true` outage suite on3101 passed **2/2** again.
Logs: `.tmp/connected-sample-final.log` and `.tmp/connected-outage-final.log`.
The 64 frontend tests and production build also passed after the chart repair.

Eight new screenshots were captured and visually inspected; original screenshots
were preserved. This is bounded visual/keyboard QA, not a formal screen-reader audit.

| Screenshot | Verified view |
| --- | --- |
| [Connected desktop](images/connected-home-1440.png) | Live workspace, runtime metadata, clear sample entry |
| [Connected tablet](images/connected-home-768.png) | Navigation and live controls fit |
| [Connected mobile](images/connected-home-390.png) | Stacked live workflow and explicit sample boundary |
| [Skills desktop](images/connected-skills-1440.png) | Selected run, reason, immutable hash/body and5-skill catalog |
| [Skills tablet](images/connected-skills-768.png) | Same evidence and readable controls |
| [Skills mobile](images/connected-skills-390.png) | Wrapped metadata/hash and scrollable exact instructions |
| [Completed execution](images/connected-completed.png) | Actual result, approval and trace bars within tracks |
| [Actual memory](images/connected-memory.png) | Originating conversation plus one final outcome event |

A separate production review console is available at `http://localhost:3102`
with API8100 and fresh `.tmp/connected-review-20261023/app.db`. It contains a
synthetic completed calculation and pending task request (no task write executed).
The review approval timeout is3600s; later expiry is normal. Existing8000/3200
processes and their database were not reused. Recreate this local review session
using the setup guide; these are local process endpoints, not public hosting.
