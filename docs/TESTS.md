# Test types

## Current portfolio milestone — 2026-10-23 (audit refresh)

The full local Python suite has **360 passed, 1 skipped** (361 collected). The
focused skills command passes **32** tests as a separately executed subset.
Ruff check/format (90 files), Pyright, canonical/strict evidence, package
contents and isolated wheel imports pass. Native protocol/fixture checks are 31
passed/1 host skip; there were no native CLI/model trials. The skipped case
requires real Windows symlink permission.

Frontend (Next.js 16, React 19, Vitest 5, ESLint 9 flat config): **64 unit
tests**, clean lint and production build of all 11 routes; **21 sample+a11y**
(13 scenario/smoke + 8 axe-core WCAG 2.1 A/AA route scans), **2 connected
outage**, **21 production-bundle** (same sample+a11y specs against `next build`
+ `next start`) and **10 real-process live** Chromium tests. Independent
screenshot inspection covers 390×844, 768×1024 and 1440×900. A healthy connected
browser probe exercises actual strict API/SQLite/task creation, completed
approval and duplicate 409, confirming one task in SQL. Sample inspection sees
zero backend/external requests/errors. `npm audit --omit=dev` reports zero
production advisories; nine dev-chain advisories remain in build/lint tooling
(tailwindcss 3.x glob/postcss chains and the bundled fast-glob inside
`@next/eslint-plugin-next`), none of which ships to the client bundle.

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

## Connected regression gates (2026-10-23)

`tests/test_connected_skills.py` covers all tool matches, explicit/unmatched and
bounded multi-step selection, concurrent session isolation, invalid/escaped
sources and historical body/hash preservation. `tests/test_connected_application.py`
covers actual HTTP handlers, migrated SQLite, skill snapshots, sessions, approval
results/traces, once-only memory and restart recovery. `tests/test_connected_evidence.py`
rejects tampering and resealed false claims.

From frontend, run `npm run test:e2e -- --config playwright.live.config.ts --project=chromium`.
This uses real dedicated processes and a disposable migrated database with no
successful-response mocks. It does not use the owner's database or credentials.
See [connected proof](portfolio-connected.md#reproduce-the-connected-proof) and the
[current verification record](portfolio-verification.md). Sample tests remain a
separate no-backend gate. Native trials and hosted CI remain separate/unverified.
