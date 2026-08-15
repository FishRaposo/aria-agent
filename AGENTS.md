# AGENTS.md — aria-agent

ARIA is a controlled, offline-first agent harness. Work from the repository
itself: the project is self-contained and must not acquire sibling-directory,
Git-installed, hosted-database, or provider-credential requirements.

## Canonical commands

```bash
python -m pip install -e ".[dev]"
pytest -q
pytest --noconftest tests/test_skills.py -q
ruff check src/aria tests examples scripts
ruff format --check src/aria tests examples scripts
pyright src/
make evidence
make package
make forbidden
```

The frontend uses its own lockfile:

```bash
cd frontend
npm ci
npm test -- --run
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e -- --project=chromium
```

The 2026-08-14 finalization snapshot is 200 passing Python tests, 12 passing
focused skill tests (a separately executed subset), Ruff check plus 72
format-clean files, and Pyright with 0 errors. Treat these as dated evidence,
not permanent expected counts; update `README.md` and `docs/TESTS.md` when the
suite changes.

## Architecture rules

- `src/aria/internal/core/` owns execution contracts, planning, safety, retry,
  rate-limit, replay, streaming events, and local memory indexing.
- Public modules (`aria.agents`, `aria.routing`, `aria.tools`,
  `aria.approvals`, `aria.memory`, `aria.costs`, `aria.tracing`) are compatibility
  facades. Preserve existing imports, response keys, route vocabulary, approval
  states, cost semantics, and `AriaAgent.run()` string behavior.
- `src/aria/internal/vendor_core/` contains only the server-used compatibility
  subset of the archived v1.3.0 source. Preserve attribution and do not restore
  an external package dependency.
- Offline defaults are `planning_mode=single`, `safety_mode=warn`, no retries,
  no rate limit, no memory retrieval requirement, and in-memory stores.
- Multi-hop, safety blocking, retries, rate limits, SSE, replay, local memory,
  and the approval sweeper are opt-in/additive capabilities.
- Risky tools remain approval-gated in `approval_gated` mode. Dry-run replay is
  the default and must not execute side effects.

## Evidence and provenance

`make evidence` is the canonical portfolio demonstration. Generated artifacts
are ignored; only the normalized fixture under
`tests/fixtures/golden/portfolio-evidence.json` is tracked. Do not put tokens,
keys, environment paths, timestamps, random IDs, or runtime durations in the
fixture. Run the dependency scan after changing build or documentation files.

The vendored source, license, and source commit are recorded in
`THIRD_PARTY_NOTICES.md`. See `docs/EVIDENCE.md` for the redaction and replay
contract.

## Tests before changing score-sensitive behavior

Capture or update golden outputs first. Keep tests for tools, routing, approval
transitions, stores, worker helpers, costs, tracing, skills, API wire shapes,
execution policies, and evidence. A refactor is not complete until the full
offline suite and the focused skills suite pass.

## Documentation boundaries

Update architecture, setup, security, failure-mode, roadmap, and evidence docs
when behavior changes. Mark historical implementation plans as historical. Keep
hosted/team workflows, external notifications, OTLP protobuf/gRPC, mandatory
infrastructure, and real provider credentials explicitly deferred.

## Git discipline

Before edits, pull/rebase the current branch. Commit ARIA, the public site, and
hub receipt changes separately. Before handoff run `git diff --check`, the
forbidden scan, the receipt checker, `node check-hub.mjs`, and `node sync-repos.mjs`.
Do not remove the queue copy until the receipt is green and the owner has the
manual visual/positioning-QA handoff.
