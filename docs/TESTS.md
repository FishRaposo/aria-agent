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
