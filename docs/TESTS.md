# Test types

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

The frontend passed 31 Vitest tests, ESLint, and a production build. Playwright
discovered six Chromium smoke tests. The browser binary was unavailable on the
local Windows verification host, so local browser execution is not claimed
green; CI installs Chromium explicitly before running the suite.
