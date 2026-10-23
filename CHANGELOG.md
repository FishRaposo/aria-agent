# Changelog

## 2026-10-23 — in-place audit refresh (1.1.0)

- Bounded session reconciliation: each process walks full session history once,
  then only scans runs saved since its latest reconciled boundary (both stores
  accept `since_created_at`; the boundary run is always re-checked). Session
  approval filtering now uses lightweight run-id projections instead of
  loading full run bodies.
- Migrated the console to Next.js 16 + React 19 (Turbopack), Vitest 5
  (`vmThreads`), and ESLint 9 flat config; `npm run lint` now calls `eslint .`
  directly since `next lint` was removed upstream. Production `npm audit`
  reports zero advisories.
- Added an axe-core WCAG 2.1 A/AA browser spec covering all eight demo routes;
  fixed the flagged contrast defects (muted ink-500/600 text raised to the AA
  floor, approve action darkened to emerald-700).
- Added production-bundle (`test:e2e:prod`, separate `.next-demo` dist) and
  connected-outage (`test:e2e:connected`) Playwright entrypoints; CI now runs
  the sample+a11y suite in both dev and production bundles plus the outage
  suite.
- Added the app icon and social/Open Graph metadata; corrected stale counts
  and connected-milestone claims across docs; bumped the package to 1.1.0.

## 2026-10-23 — connected application and controlled-execution portfolio milestone

- Bound every approval to an immutable action/arguments/run/expiry snapshot with
  durable single-use execution claims in memory and SQL; uncertain outcomes are
  never retried automatically (at-most-once dispatch).
- Added the strict portfolio launch profile (`AGENT_MODE=approval_gated` +
  `ARIA_SAFETY_MODE=block`): schema/tool/workspace validation at dispatch,
  no request-side mode downgrade, and explicit local CORS origins.
- Shipped five canonical `.agents/skills` packaged into wheel resources with
  automatic per-run selection, explicit `/skill` overrides, and immutable saved
  bodies/hashes per run (`GET /skills`).
- Added session-isolated conversation memory (`GET /agent/memory`), migration
  `0003_connected_app`, and once-only reconciled approval outcome events.
- Connected the dashboard to real session/run/approval/memory evidence with a
  separate, explicitly labeled sample provider; added a real-process browser
  suite (production Next + FastAPI + migrated disposable SQLite).
- Added the self-contained `examples/coding_agent_setup` native fixture:
  install/uninstall, blocking hooks, independent verifier, and a fixed
  ten-task benchmark runner. Native Claude Code trials remain unavailable;
  all 60 cells report unrun.

## 2026-08-14 — comprehensive local-core finalization

- Vendored the pinned server compatibility subset and removed the archived
  sibling-package installation path.
- Added bounded multi-hop planning, deterministic safety, safe-tool retries,
  fixed-window rate limits, ordered SSE events, dry-run replay, local memory
  search, and an optional approval sweeper.
- Added a redacted, checksummed offline evidence bundle with a golden fixture.
- Aligned packaging, wheel checks, CI, dashboard lint/build/browser gates, docs,
  public catalog copy, and MIT attribution.
- Recorded the finalization verification snapshot: 200 Python tests, 12 focused
  skill tests, Ruff check plus 72 format-clean files, and Pyright with 0 errors.
