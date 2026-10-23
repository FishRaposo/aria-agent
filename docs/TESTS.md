# Test types

## Current portfolio milestone — 2026-10-22–23

The full local Python suite has **302 passed, 1 skipped**. Focused skills pass12
tests as a separately executed subset. Ruff check/format (85 files), Pyright,
canonical/strict evidence, package contents and isolated wheel imports pass.
Native protocol/fixture checks are31 passed/1 host skip; there were no native
CLI/model trials. The skipped case requires real Windows symlink permission.

Frontend: **43 unit tests**, clean lint and production build; **13 sample** and
**2 connected outage** Chromium tests. Independent screenshot inspection covers
390×844, 768×1024 and1440×900. A healthy connected browser probe exercises actual
strict API/SQLite/task creation, completed approval and duplicate409, confirming
one task in SQL. Sample inspection sees zero backend/external requests/errors.

The dated [verification record](portfolio-verification.md) contains commands,
red/green findings, screenshots, exact scope and host/CI limitations. It supersedes
the historical snapshot below for this branch. No native-model score or fresh
hosted CI result is inferred from local protocol/UI checks.

- Unit tests cover tools, routing, stores, approvals, costs, traces, safety,
  retries, rate limits, memory ranking, contracts, and evidence serialization.
- Integration tests cover the agent loop, API wire compatibility, SSE/replay,
  worker helpers, and the offline golden scenario.
- Focused skill tests run without the shared application fixtures.
- Package gates build a wheel, inspect vendored contents, and import the server
  from an isolated environment.
- Frontend gates run Vitest, ESLint, a production build, and a Chromium smoke
  suite on an isolated port.

## Verified finalization snapshot

On 2026-08-14, the full Python suite passed 200 tests. The focused
progressive-disclosure command passed 12 tests; it is a separately executed
subset and is not added to the 200-test count. Ruff check passed, Ruff reported
all 72 scoped files format-clean, and Pyright reported 0 errors.

The frontend passed 31 Vitest tests, ESLint, and a production build. On
2026-08-15, all six Playwright smoke tests passed locally in Chromium. CI
installs Chromium explicitly before running the same suite.
